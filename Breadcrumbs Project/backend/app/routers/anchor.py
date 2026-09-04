"""
The RSA accumulator, its epochs, and the three-check verification.

Two things in this module are easy to get wrong and expensive to get wrong.

The first is the wire format. A 3072-bit integer is silently destroyed by every
JSON parser that maps numbers to doubles, and the frontend has one, so every
group element crosses as a hex string. `_no_bare_bigints` walks each response
and refuses to serve one that has slipped through as a number — a regression
here would corrupt proofs quietly rather than loudly, so it is worth a guard.

The second is verification. `model/anchoring.py:verify_record` runs three
independent checks and returns one boolean; this router runs the same three and
reports them separately, because collapsing them into a single green tick
discards the entire defence against a trusted-dealer forgery. See the docstring
on `verify_record` below.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from model import anchoring
from model.accumulator import RSAGroup, vdf, verify_membership, verify_non_membership
from model.chaincode.anchor import record_element
from model.consortium import DOCUMENT_CHANNEL

from .. import ledger_service as ledger
from ..auth import CurrentUser, require_capability
from ..config import ROLES, settings
from ..scoping import scoped_records

router = APIRouter(tags=["anchor"])

SAFE_INT = 2**53 - 1


def now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _no_bare_bigints(value: Any, path: str = "$") -> Any:
    """
    Refuse to serve an integer JavaScript cannot hold.

    Not defensive programming for its own sake: the accumulator's whole output
    is 3072-bit integers, and the failure mode of getting this wrong is a proof
    that looks fine and does not verify.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and abs(value) > SAFE_INT:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {
                "code": "BIGINT_ON_THE_WIRE",
                "message": (
                    f"{path} would be serialised as a JSON number with "
                    f"{value.bit_length()} bits; it must cross as a hex string."
                ),
            },
        )
    if isinstance(value, dict):
        return {k: _no_bare_bigints(v, f"{path}.{k}") for k, v in value.items()}
    if isinstance(value, list):
        return [_no_bare_bigints(v, f"{path}[{i}]") for i, v in enumerate(value)]
    return value


def _group_entry(role: str) -> dict | None:
    return ledger.query(DOCUMENT_CHANNEL, "anchor", "get_group", {}, role)


def _state(role: str) -> dict | None:
    return ledger.query(DOCUMENT_CHANNEL, "anchor", "get_state", {}, role)


class EpochRequest(BaseModel):
    """Which committed things to fold in. `kind` is "record" or "seal"."""

    items: list[dict[str, str]] = Field(min_length=1)


class BeaconRequest(BaseModel):
    epoch: int = Field(ge=0)
    iterations: int = Field(gt=0)
    # Defaulted from settings rather than required from the caller. The contract
    # compares the submitted work against the submitted minimum, so leaving this
    # open would let a publisher pass zero and satisfy the check trivially.
    minimum_iterations: int = Field(default=settings.anchor_minimum_iterations, ge=0)


class VerifyRequest(BaseModel):
    # Optional: what the caller believes the record's root to be. Supplying it
    # turns check 1 from "the ledger has something" into "the ledger has this".
    merkle_root: str | None = None


class NonMembershipRequest(BaseModel):
    reference: str = Field(min_length=1)


# --------------------------------------------------------------------------
# read-only
# --------------------------------------------------------------------------
@router.get("/anchor/state")
def anchor_state(user: CurrentUser) -> dict:
    """
    The accumulator in one integer, plus how many elements are inside it.

    Returns `installed: false` rather than an error when no ceremony has been
    run on this channel. A mechanism that is off has to be visibly off.
    """
    require_capability(user, "read_anchor")
    state = _state(user.role)
    if state is None:
        return {
            "installed": False,
            "reason": "no accumulator parameters have been installed on this channel",
        }
    return _no_bare_bigints({
        "installed": True,
        **state,
        # The delay work one epoch is expected to carry. The interface compares a
        # beacon against it, so it has to come from the same place the publisher
        # reads it from rather than being a constant typed into the frontend.
        "minimum_iterations": settings.anchor_minimum_iterations,
    })


@router.get("/anchor/group")
def anchor_group(user: CurrentUser) -> dict:
    """
    The group parameters and the ceremony that produced them.

    The transcript ships with the parameters on purpose. The modulus came from a
    trusted dealer, so anyone relying on this must be able to see who the dealer
    was and decide what that is worth to them.
    """
    require_capability(user, "read_anchor")
    entry = _group_entry(user.role)
    if entry is None:
        return {"installed": False, "reason": "no accumulator parameters on this channel"}
    return _no_bare_bigints({"installed": True, **entry})


@router.get("/anchor/epochs")
def list_epochs(user: CurrentUser) -> list[dict]:
    require_capability(user, "read_anchor")
    return _no_bare_bigints(
        ledger.query(DOCUMENT_CHANNEL, "anchor", "list_digests", {}, user.role)
    )


@router.get("/anchor/epochs/{number}")
def get_epoch(number: int, user: CurrentUser) -> dict:
    require_capability(user, "read_anchor")
    digest = ledger.query(
        DOCUMENT_CHANNEL, "anchor", "get_digest", {"epoch": number}, user.role
    )
    if digest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no epoch {number}")
    return _no_bare_bigints(digest)


@router.get("/anchor/anchored/{prime_hex}")
def is_anchored(prime_hex: str, user: CurrentUser) -> dict:
    """Was this element ever admitted by an epoch, and which one?"""
    require_capability(user, "read_anchor")
    entry = ledger.query(
        DOCUMENT_CHANNEL, "anchor", "is_anchored", {"prime_hex": prime_hex}, user.role
    )
    return _no_bare_bigints({"anchored": entry is not None, "entry": entry})


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------
@router.post("/anchor/epochs", status_code=status.HTTP_201_CREATED)
def advance_epoch(body: EpochRequest, user: CurrentUser) -> dict:
    """
    Fold a batch into the accumulator: one ledger write for the whole batch.

    The proof of exponentiation is computed here and re-checked by the contract.
    That is a client computing a proof, not a second copy of a rule — if this
    layer gets it wrong the contract refuses, which is the correct outcome.
    """
    require_capability(user, "write_anchor")
    items = [(i["kind"], i["key"]) for i in body.items]
    try:
        response = anchoring.anchor_epoch(
            ledger.consortium(),
            DOCUMENT_CHANNEL,
            items,
            now(),
            submitter=ROLES[user.role]["identity"],
        )
    except (RuntimeError, KeyError) as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"code": "EPOCH_REJECTED", "message": str(exc)},
        ) from exc
    return _no_bare_bigints(response)


@router.post("/anchor/beacon")
def publish_beacon(body: BeaconRequest, user: CurrentUser) -> dict:
    """
    Attach a delay proof to an epoch, bounding how fast history can be made.

    The input is re-derived by the contract from the previous digest and checked
    against what is submitted, so computing it here cannot be used to choose a
    convenient one.
    """
    require_capability(user, "write_anchor")
    entry = _group_entry(user.role)
    if entry is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"code": "NO_GROUP", "message": "no accumulator parameters on this channel"},
        )
    group = RSAGroup.from_dict(entry["params"])

    digest = ledger.query(
        DOCUMENT_CHANNEL, "anchor", "get_digest", {"epoch": body.epoch}, user.role
    )
    if digest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no epoch {body.epoch}")
    previous = ledger.query(
        DOCUMENT_CHANNEL, "anchor", "get_digest", {"epoch": body.epoch - 1}, user.role
    )
    seed_source = previous["digest"] if previous else digest["parameters_hash"]
    x = group.element_from({"beacon_seed": seed_source, "epoch": body.epoch})
    y, proof = vdf.evaluate(group, x, body.iterations)

    try:
        return _no_bare_bigints(
            ledger.invoke(
                DOCUMENT_CHANNEL, "anchor", "publish_beacon",
                {
                    "epoch": body.epoch,
                    "output_hex": format(y, "x"),
                    "proof": proof,
                    "minimum_iterations": body.minimum_iterations,
                    "timestamp": now(),
                },
                user.role,
            )
        )
    except ledger.LedgerError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"code": exc.code, "message": exc.message},
        ) from exc


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------
@router.post("/records/{record_id}/verify")
def verify_record(record_id: str, body: VerifyRequest, user: CurrentUser) -> dict:
    """
    Three independent checks, reported separately. This is the point of the endpoint.

      1. The ledger holds the record, with the root being claimed. A trapdoor
         holder cannot manufacture this: it needs a block, an ordering quorum and
         an endorsement.
      2. The accumulator witness verifies. Cheap, stateless — and the ONLY one a
         holder of the modulus factorisation can forge. There is a passing test
         in the model that does exactly that.
      3. The prime appears in the anchored index, written by the epoch that
         admitted it. A forged witness has no anchored entry.

    Collapsing these into one badge would show a forged record as verified while
    checks 1 and 3 were quietly failing. The response therefore carries three
    rows, and `verified` is their conjunction — not a separate opinion.
    """
    require_capability(user, "verify_anchor")

    record = next((r for r in scoped_records(user) if r["record_id"] == record_id), None)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no record {record_id}")

    entry = _group_entry(user.role)
    state = _state(user.role)
    if entry is None or state is None:
        return {
            "record_id": record_id,
            "anchored": False,
            "reason": "no accumulator parameters have been installed on this channel",
        }

    group = RSAGroup.from_dict(entry["params"])
    element = record_element(record)

    # Check 1 — the ledger.
    claimed = body.merkle_root or record["merkle_root"]
    ledger_ok = record["merkle_root"] == claimed
    checks = [
        {
            "id": "ledger",
            "label": "The ledger holds this record, with this root",
            # Every check carries a second wording. The technical one is what an
            # engineer needs and the only one this endpoint used to send, which
            # meant a buyer reading a record page was shown three sentences
            # about accumulators and asked to conclude something from them.
            "plain_label": "The ledger has this record, and it matches",
            "ok": ledger_ok,
            "detail": (
                f"committed in {record['bucket']} by {record['owner_msp']}"
                if ledger_ok
                else "the root on the ledger is not the root being claimed"
            ),
            "plain_detail": (
                f"Published by {record['owner_msp'].replace('MSP', '')} and unchanged since"
                if ledger_ok
                else "The fingerprint on the ledger is not the one being claimed"
            ),
            "forgeable_by_trapdoor": False,
        }
    ]

    # Check 2 — the witness. Issued from state, then verified against it.
    try:
        acc = anchoring.accumulator_from_ledger(
            ledger.consortium(), DOCUMENT_CHANNEL, ledger.identity_for(user.role)
        )
        witness = acc.membership_witness(element)
        witness_ok, witness_why = verify_membership(
            group, int(state["value_hex"], 16), witness, element, int(state["epoch"])
        )
    except Exception as exc:  # noqa: BLE001 — surfaced, not swallowed
        witness, witness_ok, witness_why = None, False, str(exc)

    checks.append(
        {
            "id": "witness",
            "label": "The accumulator witness verifies",
            "plain_label": "It is covered by the network's tamper check",
            "ok": witness_ok,
            "detail": witness_why or f"verified against epoch {state['epoch']}",
            "plain_detail": (
                witness_why
                or "The single number that covers the whole ledger accounts for this record"
            ),
            # Stated on the wire so the interface cannot forget to say it.
            "forgeable_by_trapdoor": True,
        }
    )

    # Check 3 — the anchored index.
    anchored = None
    if witness is not None:
        anchored = ledger.query(
            DOCUMENT_CHANNEL, "anchor", "is_anchored",
            {"prime_hex": format(witness.element_prime, "x")}, user.role,
        )
    index_ok = anchored is not None and anchored.get("key") == record_id
    checks.append(
        {
            "id": "index",
            "label": "The element is in the anchored index",
            "plain_label": "It was actually added, on a date, in the open",
            "ok": index_ok,
            "detail": (
                f"admitted by epoch {anchored['epoch']}"
                if index_ok
                else "no epoch ever admitted this element; the witness was not issued by one"
            ),
            "plain_detail": (
                "There is a public entry recording when this was added"
                if index_ok
                else "Nothing on the ledger records this ever being added"
            ),
            "forgeable_by_trapdoor": False,
        }
    )

    combined, why = anchoring.verify_record(
        ledger.consortium(), DOCUMENT_CHANNEL, record_id, witness, ledger.identity_for(user.role)
    ) if witness is not None else (False, witness_why)

    # The itemised result must agree with the model's own verifier, but only
    # over what that verifier actually covers. It asks whether the ledger holds
    # the record at all; check 1 above asks the stronger question of whether it
    # holds it with the root the caller is claiming. The two legitimately differ
    # when a caller presents a root the ledger does not have — and that case has
    # to fail, not raise. So the guard compares like with like, and any
    # divergence inside the shared scope is a defect rather than a verdict.
    model_scope = witness_ok and index_ok
    if combined != model_scope:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            {
                "code": "VERIFIER_DISAGREEMENT",
                "message": (
                    "the model's verifier and the itemised checks disagree over the "
                    "witness and the anchored index; this is a defect, not a verdict"
                ),
            },
        )

    verified = all(c["ok"] for c in checks)

    return _no_bare_bigints(
        {
            "record_id": record_id,
            "anchored": True,
            "epoch": int(state["epoch"]),
            "checks": checks,
            "verified": verified,
            "reason": why or (
                "" if verified else "the root being claimed is not the root on the ledger"
            ),
            "witness": witness.to_dict() if witness else None,
            "note": (
                "The modulus came from a trusted-dealer ceremony, so whoever holds its "
                "factorisation could forge check 2. Checks 1 and 3 are what make that "
                "forgery fail anyway, which is why all three are shown."
            ),
            "plain_note": (
                "Check 2 is the only one someone with the original setup secret could "
                "fake. Checks 1 and 3 would still catch them, which is why all three "
                "are run instead of one combined score."
            ),
        }
    )


@router.post("/anchor/non-membership")
def non_membership(body: NonMembershipRequest, user: CurrentUser) -> dict:
    """
    Prove a reference was never committed — the thing no Merkle tree can do.

    Two statements, kept apart because they are not the same strength:

      * the ledger holds no record under this identifier (a lookup), and
      * the canonical element for this reference was never accumulated up to the
        current epoch (a Bezout proof).

    The second is the cryptographic one, and its scope is narrow and stated: it
    covers *this* canonical form up to *this* epoch, and says nothing about
    later ones. The response carries `scope` so the screen can print it.
    """
    require_capability(user, "verify_anchor")
    entry = _group_entry(user.role)
    state = _state(user.role)
    if entry is None or state is None:
        return {
            "reference": body.reference,
            "provable": False,
            "reason": "no accumulator parameters have been installed on this channel",
        }

    group = RSAGroup.from_dict(entry["params"])
    element = {"type": "reference", "reference": body.reference}

    stored = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "get_record", {"record_id": body.reference}, user.role
    )

    acc = anchoring.accumulator_from_ledger(
        ledger.consortium(), DOCUMENT_CHANNEL, ledger.identity_for(user.role)
    )
    witness = acc.non_membership_witness(element)
    ok, why = verify_non_membership(
        group, int(state["value_hex"], 16), witness, element, int(state["epoch"])
    )

    return _no_bare_bigints(
        {
            "reference": body.reference,
            "provable": True,
            "epoch": int(state["epoch"]),
            "ledger_holds_record": stored is not None,
            "never_committed": ok and stored is None,
            "proof_ok": ok,
            "reason": why,
            "witness": witness.to_dict(),
            "scope": (
                f"This proves the canonical element for '{body.reference}' was never "
                f"accumulated up to epoch {state['epoch']}. It says nothing about later "
                "epochs, and nothing about documents that were never offered to this "
                "ledger at all."
            ),
        }
    )
