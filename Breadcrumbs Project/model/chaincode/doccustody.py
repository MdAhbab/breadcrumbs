"""
doccustody chaincode: document commitments, access grants, verification receipts.

What this contract stores is the whole argument of the report's Table 2. It holds
root hashes, record type, period, site, and who was granted access to what. It
does not hold the document, the rows, any worker's name, or any wage. Those stay
in the factory's own encrypted storage, because an append-only ledger and a
deletion right cannot both be satisfied for personal data.

Access grants are on-chain for a reason worth saying out loud: a buyer must not
be able to deny that access was granted, and a factory must not be able to deny
granting it. A grant held in a vendor's database satisfies neither party.

Determinism: no clocks, no randomness. Every timestamp arrives as an argument
from the client so all endorsers see the same value.
"""

from __future__ import annotations

from typing import Any

from ..ledger.crypto import verify
from ..ledger.network import ChaincodeError, Context
from ..merkle import Disclosure, ProofStep, public_root, verify_disclosure
from .witness import (
    CHECK_CODES,
    WITNESS_QUORUM,
    assign_witnesses,
    attestation_payload,
    is_witnessed,
    seed_from_shares,
    share_commitment,
)

RECORD = "record:"
GRANT = "grant:"
RECEIPT = "receipt:"
SEAL = "seal:"
SEEDROUND = "seedround:"
FINDING = "finding:"
ACTIVE_SEED = "active_seed"

VALID_TYPES = {
    "payroll_register",
    "safety_inspection",
    "chemical_inventory",
    "machine_maintenance",
    "compliance_certificate",
}


def _require_factory(ctx: Context) -> None:
    kind = ctx.msp.org_kind(ctx.caller_msp)
    ctx.require(kind == "factory", f"{ctx.caller_msp} is not a factory organisation")


def open_seed_round(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Start a commit-reveal round for the witness-assignment seed.

    Adopting the witness rule is a governed act, not a configuration flag. Until
    a round has closed there is no seed, no assignment can be computed, and the
    contract does not require counter-signatures — which is the correct behaviour
    for a consortium that has not yet agreed to the rule, and is why the
    interface has to show whether the rule is in force rather than assume it.
    """
    ctx.require(
        ctx.msp.org_kind(ctx.caller_msp) == "consortium",
        "only the consortium may open a seed round",
    )
    round_id = args["round_id"]
    ctx.require(ctx.get(SEEDROUND + round_id) is None, f"seed round {round_id} already exists")
    members = sorted(set(args["members"]))
    ctx.require(len(members) >= 2, "a seed round needs at least two contributors")
    sample = int(args["sample_percent"])
    ctx.require(0 <= sample <= 100, "sample_percent must be a percentage")

    ctx.put(
        SEEDROUND + round_id,
        {
            "round_id": round_id,
            "members": members,
            "sample_percent": sample,
            "quorum": int(args.get("quorum", WITNESS_QUORUM)),
            "commitments": {},
            "shares": {},
            "seed": None,
            "status": "committing",
            "opened_at": args["timestamp"],
        },
    )
    return {"round_id": round_id, "members": members, "status": "committing"}


def commit_seed_share(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """Publish the hash of your share, before anybody has revealed theirs."""
    rnd = ctx.get(SEEDROUND + args["round_id"])
    ctx.require(rnd is not None, f"unknown seed round {args['round_id']}")
    ctx.require(rnd["status"] == "committing", f"round is {rnd['status']}")
    ctx.require(ctx.caller_msp in rnd["members"], f"{ctx.caller_msp} is not in this round")
    ctx.require(ctx.caller_msp not in rnd["commitments"], "already committed")
    ctx.require(len(args["commitment"]) == 64, "a commitment is a 64-character hash")

    updated = dict(rnd)
    updated["commitments"] = {**rnd["commitments"], ctx.caller_msp: args["commitment"]}
    if len(updated["commitments"]) == len(rnd["members"]):
        updated["status"] = "revealing"
    ctx.put(SEEDROUND + args["round_id"], updated)
    return {"round_id": args["round_id"], "status": updated["status"],
            "committed": len(updated["commitments"])}


def reveal_seed_share(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Reveal your share. The contract checks it against what you committed.

    Without this check the commit phase would be theatre: a member could commit
    to anything and then reveal whatever value made the assignment come out the
    way it wanted, which is precisely the grinding attack the two phases exist to
    prevent.
    """
    rnd = ctx.get(SEEDROUND + args["round_id"])
    ctx.require(rnd is not None, f"unknown seed round {args['round_id']}")
    ctx.require(rnd["status"] == "revealing", f"round is {rnd['status']}; all members must commit first")
    ctx.require(ctx.caller_msp in rnd["members"], f"{ctx.caller_msp} is not in this round")
    ctx.require(ctx.caller_msp not in rnd["shares"], "already revealed")

    share = args["share"]
    ctx.require(
        share_commitment(share) == rnd["commitments"][ctx.caller_msp],
        "the revealed share does not match the commitment",
    )

    updated = dict(rnd)
    updated["shares"] = {**rnd["shares"], ctx.caller_msp: share}
    if len(updated["shares"]) == len(rnd["members"]):
        updated["seed"] = seed_from_shares(updated["shares"])
        updated["status"] = "closed"
        updated["closed_at"] = args["timestamp"]
        ctx.put(ACTIVE_SEED, args["round_id"])
    ctx.put(SEEDROUND + args["round_id"], updated)
    return {
        "round_id": args["round_id"],
        "status": updated["status"],
        "revealed": len(updated["shares"]),
        "seed": updated["seed"],
    }


def _active_round(ctx: Context) -> dict[str, Any] | None:
    """The seed round currently governing witness assignment, if the rule is in force."""
    round_id = ctx.get(ACTIVE_SEED)
    if round_id is None:
        return None
    rnd = ctx.get(SEEDROUND + round_id)
    return rnd if rnd and rnd["status"] == "closed" else None


def _witness_pool(ctx: Context, owner_msp: str) -> list[str]:
    """
    Who may witness for this owner: any factory or auditor on the channel but not
    the owner itself. Derived from the channel configuration rather than a list
    somebody maintains, so adding a member to the channel adds them to the pool
    and nobody has to remember to.
    """
    config = ctx.get("__config__") or {}
    return sorted(
        m
        for m in config.get("members", [])
        if m != owner_msp and ctx.msp.org_kind(m) in ("factory", "auditor")
    )


def witness_requirement(ctx: Context, record_id: str, record_type: str, owner_msp: str) -> dict[str, Any]:
    """
    Read-only: is this record witnessed, and by whom? Callable before committing,
    so a factory can find out who to ask rather than guess.
    """
    rnd = _active_round(ctx)
    if rnd is None:
        return {"in_force": False, "required": False, "witnesses": [],
                "reason": "the consortium has not adopted the witness rule on this channel"}
    required = is_witnessed(rnd["seed"], record_id, record_type, rnd["sample_percent"])
    pool = _witness_pool(ctx, owner_msp)
    return {
        "in_force": True,
        "required": required,
        "round_id": rnd["round_id"],
        "witnesses": assign_witnesses(rnd["seed"], record_id, pool, rnd["quorum"]) if required else [],
        "pool_size": len(pool),
    }


def bucket_key(owner_msp: str, site: str, record_type: str, period: str) -> str:
    """
    The identifier of one owner's reporting period, at one site, for one type.

    Sealing is defined over a bucket rather than a document because the question
    a buyer actually asks is not "is this payroll register genuine" but "is this
    every payroll register Gazipur produced in July". The first is answerable by
    any notarisation service. The second is not answerable by any of them.

    The owner is part of the key and that is not cosmetic. Without it, two
    factories operating at the same site name the same bucket, and whichever
    seals second either collides or silently overwrites a statement it does not
    own. A seal is one organisation's assertion about its own records, so the
    organisation belongs in the identifier.
    """
    return f"{owner_msp}|{site}|{record_type}|{period}"


def _require_owner(ctx: Context, record: dict[str, Any]) -> None:
    ctx.require(
        record["owner_msp"] == ctx.caller_msp,
        f"{ctx.caller_msp} does not own {record['record_id']}",
    )


def commit_record(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """Commit a document's Merkle root and its metadata. Nothing else."""
    _require_factory(ctx)
    ctx.require(ctx.caller_role in ("operator", "admin"), "role may not commit records")

    record_id = args["record_id"]
    ctx.require(ctx.get(RECORD + record_id) is None, f"{record_id} already committed")
    ctx.require(
        args["record_type"] in VALID_TYPES,
        f"unknown record type {args['record_type']}",
    )

    # Once a period is sealed its membership is fixed. Adding to it afterwards is
    # not forbidden — sometimes a record genuinely arrives late — but it cannot
    # happen silently. The owner must first reopen the period, which is permanent,
    # counted and visible to every member, and re-seal it afterwards.
    #
    # The three steps are deliberate and the ordering is the whole point. An
    # earlier version of this contract told a caller to use amend_seal, which
    # required the record to exist already — so a genuinely late record had no
    # route in at all, and the error message described a door that was not there.
    # A caller stuck in that state has no way to comply, which is worse than a
    # refusal: it looks like the system is working and it is not.
    bucket = bucket_key(ctx.caller_msp, args["site"], args["record_type"], args["period"])
    seal = ctx.get(SEAL + bucket)
    ctx.require(
        seal is None or seal["status"] == "reopened",
        f"period {bucket} is sealed; reopen_seal it first, commit, then amend_seal. "
        "Reopening is permanent and counted.",
    )
    ctx.require(len(args["merkle_root"]) == 64, "merkle_root must be a 64-character hash")
    ctx.require(int(args["row_count"]) > 0, "a record must have at least one row")

    record = {
        "record_id": record_id,
        "owner_msp": ctx.caller_msp,
        "merkle_root": args["merkle_root"],
        "record_type": args["record_type"],
        "period": args["period"],
        "site": args["site"],
        "row_count": int(args["row_count"]),
        "bucket": bucket,
        "schema_version": args["schema_version"],
        "committed_at": args["timestamp"],
        "committed_by": ctx.caller.id,
        "status": "committed",
        "superseded_by": None,
    }
    attested = _check_attestations(ctx, record, args)
    record["witnesses"] = attested["witnesses"]
    record["attestations"] = attested["attestations"]

    ctx.put(RECORD + record_id, record)
    return {
        "record_id": record_id,
        "merkle_root": args["merkle_root"],
        "status": "committed",
        "witnesses": attested["witnesses"],
    }


def _check_attestations(ctx: Context, record: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    """
    Verify the counter-signatures, or explain why none were needed.

    The signature check follows the pattern the security audit forced on the rest
    of this codebase: the certificate is resolved through the MSP *first*, and the
    key used is the one out of that validated certificate. Verifying against a key
    the submission carried would prove only that somebody holds some private key,
    which would let a factory generate a keypair, label it with a peer's name and
    witness its own records. That is finding F-2 all over again, in a new place.
    """
    requirement = witness_requirement(
        ctx, record["record_id"], record["record_type"], record["owner_msp"]
    )
    if not requirement["required"]:
        return {"witnesses": [], "attestations": []}

    expected = requirement["witnesses"]
    submitted = args.get("attestations") or []
    ctx.require(
        bool(submitted),
        f"{record['record_id']} must be counter-signed by {', '.join(expected)}",
    )

    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for attestation in submitted:
        msp_id = attestation["witness_msp"]
        ctx.require(msp_id in expected, f"{msp_id} was not assigned to witness this record")
        ctx.require(msp_id not in seen, f"{msp_id} attested twice")
        ctx.require(
            attestation["check_code"] in CHECK_CODES,
            f"unknown check code {attestation['check_code']}",
        )

        public_key, reason = ctx.msp.public_key_for(msp_id, attestation.get("certificate_pem", ""))
        ctx.require(public_key is not None, f"{msp_id}: {reason}")

        payload = attestation_payload(record, attestation["check_code"], attestation["attested_at"])
        ctx.require(
            verify(public_key, payload, attestation["signature"]),
            f"{msp_id}: the attestation signature does not verify against what was committed",
        )

        seen.add(msp_id)
        accepted.append(
            {
                "witness_msp": msp_id,
                "check_code": attestation["check_code"],
                "attested_at": attestation["attested_at"],
                "signature": attestation["signature"],
            }
        )

    missing = [m for m in expected if m not in seen]
    ctx.require(not missing, f"missing counter-signature from {', '.join(missing)}")
    return {"witnesses": expected, "attestations": accepted}


def supersede_record(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Mark a record replaced by a later version.

    The old record is not deleted and its root stays verifiable. A correction is
    part of the history, not a replacement for it.
    """
    old = ctx.get(RECORD + args["record_id"])
    ctx.require(old is not None, f"unknown record {args['record_id']}")
    _require_owner(ctx, old)
    new = ctx.get(RECORD + args["new_record_id"])
    ctx.require(new is not None, f"unknown replacement record {args['new_record_id']}")

    old = dict(old)
    old["status"] = "superseded"
    old["superseded_by"] = args["new_record_id"]
    old["supersede_reason"] = args["reason"]
    old["superseded_at"] = args["timestamp"]
    ctx.put(RECORD + args["record_id"], old)
    return {"record_id": args["record_id"], "status": "superseded"}


def seal_period(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Close a reporting period and fix, permanently, exactly which records it holds.

    This is the mechanism behind the report's strongest claim, so it is worth
    saying precisely what it does and does not do.

    WHAT IT DOES. The contract enumerates every record the ledger holds for this
    bucket and refuses to seal unless the declared list matches it exactly. It
    then commits the count and a Merkle root over the sorted identifiers. A
    factory that later discloses a subset produces a different root and a
    different count, and any verifier holding the seal catches it without needing
    to ask anyone whether the list was complete. Withholding stops being an
    invisible act and becomes an arithmetic contradiction.

    WHAT IT DOES NOT DO. It cannot make a factory commit a record it never
    committed. If a payroll register was kept entirely off the ledger, the seal
    is internally consistent and says nothing. That residual is the first-mile
    problem, and the answer to it is not here — it is the independent attesting
    witness, the cross-checks against production and electricity records, and the
    amendment-rate statistics. Anyone presenting this seal as a solution to
    fraud rather than to *withholding* is overstating it.
    """
    _require_factory(ctx)
    ctx.require(ctx.caller_role in ("operator", "admin"), "role may not seal a period")
    ctx.require(args["record_type"] in VALID_TYPES, f"unknown record type {args['record_type']}")

    bucket = bucket_key(ctx.caller_msp, args["site"], args["record_type"], args["period"])
    existing = ctx.get(SEAL + bucket)
    ctx.require(
        existing is None,
        f"{bucket} is already sealed; use amend_seal to change a closed period",
    )

    # The range scan is what makes this honest, and it is why Context.range
    # records a digest of the keys it saw: a record committed concurrently would
    # otherwise slip past the check and the seal would be wrong from birth.
    on_ledger = sorted(
        r["record_id"] for _, r in ctx.range(RECORD) if r["bucket"] == bucket
    )
    ctx.require(
        bool(on_ledger),
        f"{ctx.caller_msp} has committed no records to {bucket}; there is nothing to seal",
    )
    declared = sorted(args["record_ids"])

    ctx.require(len(set(declared)) == len(declared), "the declared list repeats a record")
    missing = [r for r in on_ledger if r not in set(declared)]
    ctx.require(
        not missing,
        f"the declared list omits {len(missing)} record(s) the ledger holds for {bucket}: "
        + ", ".join(missing[:5]),
    )
    unknown = [r for r in declared if r not in set(on_ledger)]
    ctx.require(
        not unknown,
        f"the declared list names {len(unknown)} record(s) not committed to {bucket}: "
        + ", ".join(unknown[:5]),
    )

    entry = {
        "bucket": bucket,
        "site": args["site"],
        "record_type": args["record_type"],
        "period": args["period"],
        "owner_msp": ctx.caller_msp,
        "record_count": len(declared),
        "records_root": public_root(declared),
        "sealed_at": args["timestamp"],
        "sealed_by": ctx.caller.id,
        "status": "sealed",
        "version": 1,
        "amendments": [],
    }
    ctx.put(SEAL + bucket, entry)
    return {
        "bucket": bucket,
        "record_count": entry["record_count"],
        "records_root": entry["records_root"],
        "status": "sealed",
    }


def reopen_seal(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Reopen a closed period so a genuinely late record can be committed into it.

    Reopening is the visible half of the amendment. It is recorded before the new
    record exists, with a reason, which means the declaration of intent is on the
    ledger ahead of the thing being declared — a factory cannot reopen a period,
    find nothing worth adding, and quietly pretend it never asked.

    A reopened period is not sealed. Any completeness check against it says so
    rather than reporting the stale count as though it still held, because a
    verifier reading a count that is mid-revision needs to know that is what it is
    looking at.
    """
    _require_factory(ctx)
    ctx.require(ctx.caller_role in ("operator", "admin"), "role may not reopen a period")

    bucket = bucket_key(ctx.caller_msp, args["site"], args["record_type"], args["period"])
    seal = ctx.get(SEAL + bucket)
    ctx.require(seal is not None, f"{bucket} has never been sealed")
    ctx.require(seal["owner_msp"] == ctx.caller_msp, f"{ctx.caller_msp} does not own {bucket}")
    ctx.require(seal["status"] == "sealed", f"{bucket} is already {seal['status']}")
    ctx.require(bool(args.get("reason")), "reopening a period must state a reason")

    updated = dict(seal)
    updated["status"] = "reopened"
    updated["reopenings"] = [
        *seal.get("reopenings", []),
        {
            "at_version": seal["version"],
            "count_when_reopened": seal["record_count"],
            "root_when_reopened": seal["records_root"],
            "reason": args["reason"],
            "reopened_at": args["timestamp"],
            "reopened_by": ctx.caller.id,
        },
    ]
    ctx.put(SEAL + bucket, updated)
    return {
        "bucket": bucket,
        "status": "reopened",
        "reopening_count": len(updated["reopenings"]),
        "reason": args["reason"],
    }


def amend_seal(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Add records to a closed period, permanently and visibly.

    An amendment is not an edit. The previous seal stays in the history with its
    own count and root, the new one supersedes it, and the reason is recorded. A
    verifier looking at a period that has been amended four times can see that,
    and a factory whose amendment rate is far above its peers has told everyone
    something whether it meant to or not.

    That last effect is the point. Making a legitimate action expensive in
    reputation rather than forbidding it is what keeps the system usable by
    honest factories, which sometimes genuinely do find a record late.
    """
    _require_factory(ctx)
    ctx.require(ctx.caller_role in ("operator", "admin"), "role may not amend a seal")

    bucket = bucket_key(ctx.caller_msp, args["site"], args["record_type"], args["period"])
    seal = ctx.get(SEAL + bucket)
    ctx.require(seal is not None, f"{bucket} has never been sealed")
    ctx.require(seal["owner_msp"] == ctx.caller_msp, f"{ctx.caller_msp} does not own {bucket}")
    ctx.require(bool(args.get("reason")), "an amendment must state a reason")
    ctx.require(
        seal["status"] == "reopened",
        f"{bucket} is {seal['status']}; reopen_seal it before amending, so the "
        "intent to change a closed period is recorded before the change is made",
    )

    added = sorted(args["added_record_ids"])
    ctx.require(bool(added), "an amendment must add at least one record")
    for record_id in added:
        record = ctx.get(RECORD + record_id)
        ctx.require(record is not None, f"unknown record {record_id}")
        ctx.require(record["bucket"] == bucket, f"{record_id} does not belong to {bucket}")
        ctx.require(record["owner_msp"] == ctx.caller_msp, f"{ctx.caller_msp} does not own {record_id}")

    on_ledger = sorted(r["record_id"] for _, r in ctx.range(RECORD) if r["bucket"] == bucket)

    updated = dict(seal)
    updated["amendments"] = [
        *seal["amendments"],
        {
            "version": seal["version"],
            "previous_count": seal["record_count"],
            "previous_root": seal["records_root"],
            "added": added,
            "reason": args["reason"],
            "amended_at": args["timestamp"],
            "amended_by": ctx.caller.id,
        },
    ]
    updated["version"] = seal["version"] + 1
    updated["record_count"] = len(on_ledger)
    updated["records_root"] = public_root(on_ledger)
    updated["status"] = "sealed"  # closed again, at a new version
    ctx.put(SEAL + bucket, updated)
    return {
        "bucket": bucket,
        "version": updated["version"],
        "record_count": updated["record_count"],
        "records_root": updated["records_root"],
        "amendment_count": len(updated["amendments"]),
    }


def check_completeness(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Read-only: does a disclosed list of records match what the period was sealed with?

    A verifier can do this arithmetic entirely off-chain from the seal alone —
    that is the whole point, and it is why the seal carries a root rather than a
    list. This function exists so the interface can show the check being made,
    and so a verifier without the Merkle code can ask the ledger to do it.
    """
    bucket = bucket_key(args["owner_msp"], args["site"], args["record_type"], args["period"])
    seal = ctx.get(SEAL + bucket)
    if seal is None:
        return {"bucket": bucket, "sealed": False, "complete": False,
                "reason": "this period has never been sealed"}

    if seal["status"] == "reopened":
        return {
            "bucket": bucket,
            "sealed": False,
            "complete": False,
            "status": "reopened",
            "sealed_count": seal["record_count"],
            "disclosed_count": len(set(args["disclosed_record_ids"])),
            "reason": (
                "this period has been reopened and not yet re-sealed; its membership "
                "is mid-revision and the stale count must not be read as settled"
            ),
        }

    disclosed = sorted(set(args["disclosed_record_ids"]))
    computed = public_root(disclosed)
    complete = computed == seal["records_root"] and len(disclosed) == seal["record_count"]
    return {
        "bucket": bucket,
        "sealed": True,
        "status": seal["status"],
        "complete": complete,
        "sealed_count": seal["record_count"],
        "disclosed_count": len(disclosed),
        "sealed_root": seal["records_root"],
        "computed_root": computed,
        "amendment_count": len(seal["amendments"]),
        "reason": "" if complete else (
            f"{seal['record_count'] - len(disclosed)} record(s) were sealed into this "
            "period but not disclosed"
            if len(disclosed) < seal["record_count"]
            else "the disclosed set does not match what was sealed"
        ),
    }


def report_disclosure_mismatch(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Prove on-chain that a factory served content it did not commit.

    This is the one falsification the contract can establish *by itself*, with no
    human judgement anywhere in it: the verifier supplies exactly what it was
    given — a row, its salt, and the proof path — the contract recomputes the
    Merkle root, and either it matches the commitment or it does not. Deterministic,
    reproducible by every endorser, and reproducible by anybody reading the ledger
    afterwards.

    Note which way round the check goes. The finding is recorded only when the
    recomputed root FAILS to match. A verifier that tried to file a finding about
    a disclosure that actually verifies is told so and nothing is written, because
    a system where accusations are free is a system where they are worthless.
    """
    record = ctx.get(RECORD + args["record_id"])
    ctx.require(record is not None, f"unknown record {args['record_id']}")
    ctx.require(
        ctx.msp.org_kind(ctx.caller_msp) in ("buyer", "auditor", "regulator"),
        "only a verifying organisation may report a disclosure mismatch",
    )

    disclosure = Disclosure(
        record_id=args["record_id"],
        field_name=args["field_name"],
        value=args["value"],
        salt=args["salt"],
        index=int(args["index"]),
        path=[ProofStep(step["sibling"], step["position"]) for step in args["path"]],
    )
    matches, computed, _ = verify_disclosure(disclosure, record["merkle_root"])
    ctx.require(
        not matches,
        "this disclosure verifies against the committed root; there is nothing to report",
    )

    finding_id = args["finding_id"]
    ctx.require(ctx.get(FINDING + finding_id) is None, f"{finding_id} already exists")
    finding = {
        "finding_id": finding_id,
        "kind": "disclosure_mismatch",
        "record_id": args["record_id"],
        "owner_msp": record["owner_msp"],
        "reported_by": ctx.caller_msp,
        "committed_root": record["merkle_root"],
        "computed_root": computed,
        "established_on_chain": True,
        "reason": "the content served does not recompute to the committed root",
        "penalties": [{"msp_id": record["owner_msp"], "event_type": "disclosure_mismatch"}],
        "reported_at": args["timestamp"],
    }
    ctx.put(FINDING + finding_id, finding)

    disputed = dict(record)
    disputed["status"] = "disputed"
    disputed["disputed_by"] = finding_id
    ctx.put(RECORD + args["record_id"], disputed)
    return finding


def report_falsification(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Record an auditor's finding that a committed record was false, and who vouched.

    Be exact about what this is, because it is the one place in this system where
    a human judgement is written to an immutable ledger. The contract does NOT
    determine that a record is false — it cannot, and no contract can. What it
    does is make the finding permanent, attributable to the organisation that made
    it, and automatically consequential for everyone who signed the record: the
    owner and every witness that attested to it.

    That last part is the whole reason the witness mechanism has teeth. Attesting
    is cheap and earns a little; attesting to something later found false costs
    several times what honest attestation ever earned. A witness deciding whether
    to sign for a document it has not checked is making a bet, and the odds are
    set here.

    A finding is itself a permanent, attributable act. An auditor that files
    findings carelessly leaves exactly as legible a record as a factory that
    falsifies carelessly.
    """
    ctx.require(
        ctx.msp.org_kind(ctx.caller_msp) == "auditor",
        "only an auditor organisation may record a falsification finding",
    )
    record = ctx.get(RECORD + args["record_id"])
    ctx.require(record is not None, f"unknown record {args['record_id']}")
    ctx.require(bool(args.get("reason")), "a finding must state its reason")

    finding_id = args["finding_id"]
    ctx.require(ctx.get(FINDING + finding_id) is None, f"{finding_id} already exists")

    penalties = [{"msp_id": record["owner_msp"], "event_type": "record_falsified"}]
    for attestation in record.get("attestations", []):
        penalties.append(
            {
                "msp_id": attestation["witness_msp"],
                "event_type": "witness_of_falsified_record",
                "check_code": attestation["check_code"],
            }
        )

    finding = {
        "finding_id": finding_id,
        "kind": "falsification",
        "record_id": args["record_id"],
        "owner_msp": record["owner_msp"],
        "reported_by": ctx.caller_msp,
        "established_on_chain": False,
        "reason": args["reason"],
        "evidence_record_ids": sorted(args.get("evidence_record_ids", [])),
        "witnesses": record.get("witnesses", []),
        "penalties": penalties,
        "reported_at": args["timestamp"],
    }
    ctx.put(FINDING + finding_id, finding)

    disputed = dict(record)
    disputed["status"] = "disputed"
    disputed["disputed_by"] = finding_id
    ctx.put(RECORD + args["record_id"], disputed)
    return finding


def get_finding(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(FINDING + args["finding_id"])


def list_findings(ctx: Context, args: dict[str, Any]) -> list[Any]:
    out = [v for _, v in ctx.range(FINDING)]
    if owner := args.get("owner_msp"):
        out = [f for f in out if f["owner_msp"] == owner]
    if witness := args.get("witness_msp"):
        out = [f for f in out if witness in f.get("witnesses", [])]
    return out


def grant_access(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Grant one named organisation the right to verify one named field.

    Scope is a single field, not a document. That is the difference between this
    and sending a PDF, and the contract enforces it rather than trusting the
    application layer to remember.
    """
    record = ctx.get(RECORD + args["record_id"])
    ctx.require(record is not None, f"unknown record {args['record_id']}")
    _require_owner(ctx, record)

    grant_id = args["grant_id"]
    ctx.require(ctx.get(GRANT + grant_id) is None, f"{grant_id} already exists")
    ctx.require(
        args["requester_msp"] in ctx.msp.authorities,
        f"unknown organisation {args['requester_msp']}",
    )
    ctx.require(bool(args.get("field_name")), "a grant must name exactly one field")

    grant = {
        "grant_id": grant_id,
        "record_id": args["record_id"],
        "owner_msp": ctx.caller_msp,
        "requester_msp": args["requester_msp"],
        "purpose_code": args["purpose_code"],
        "field_name": args["field_name"],
        "granted_at": args["timestamp"],
        "expires_at": args["expires_at"],
        "status": "active",
        "revoked_reason": None,
    }
    ctx.put(GRANT + grant_id, grant)
    return {"grant_id": grant_id, "status": "active"}


def revoke_access(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """Revoke a grant. Permanent and attributable, which is the point."""
    grant = ctx.get(GRANT + args["grant_id"])
    ctx.require(grant is not None, f"unknown grant {args['grant_id']}")
    ctx.require(
        grant["owner_msp"] == ctx.caller_msp
        or ctx.msp.org_kind(ctx.caller_msp) == "consortium",
        "only the record owner or the consortium may revoke a grant",
    )
    ctx.require(grant["status"] == "active", f"grant is already {grant['status']}")

    grant = dict(grant)
    grant["status"] = "revoked"
    grant["revoked_reason"] = args["reason"]
    grant["revoked_at"] = args["timestamp"]
    grant["revoked_by"] = ctx.caller.id
    ctx.put(GRANT + args["grant_id"], grant)
    return {"grant_id": args["grant_id"], "status": "revoked"}


def record_verification(ctx: Context, args: dict[str, Any]) -> dict[str, Any]:
    """
    Log that a verification happened, and its outcome.

    The contract checks the grant is live and in scope before it will write a
    receipt. A verification outside scope is refused here, not merely logged.
    """
    grant = ctx.get(GRANT + args["grant_id"])
    ctx.require(grant is not None, f"unknown grant {args['grant_id']}")
    ctx.require(
        grant["requester_msp"] == ctx.caller_msp,
        f"grant {args['grant_id']} does not belong to {ctx.caller_msp}",
    )
    ctx.require(grant["status"] == "active", f"grant is {grant['status']}")
    ctx.require(
        grant["field_name"] == args["field_name"],
        f"grant covers {grant['field_name']}, not {args['field_name']}",
    )
    ctx.require(
        args["timestamp"] <= grant["expires_at"],
        f"grant expired on {grant['expires_at']}",
    )

    receipt = {
        "receipt_id": args["receipt_id"],
        "grant_id": args["grant_id"],
        "record_id": grant["record_id"],
        "verifier_msp": ctx.caller_msp,
        "field_name": args["field_name"],
        "result": args["result"],  # "match" or "no_match"
        "computed_root": args["computed_root"],
        "verified_at": args["timestamp"],
    }
    ctx.put(RECEIPT + args["receipt_id"], receipt)
    return receipt


# -- read-only ------------------------------------------------------------
def witness_requirement_route(ctx: Context, args: dict[str, Any]) -> Any:
    return witness_requirement(
        ctx, args["record_id"], args["record_type"], args.get("owner_msp", ctx.caller_msp)
    )


def get_seed_round(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(SEEDROUND + args["round_id"])


def get_record(ctx: Context, args: dict[str, Any]) -> Any:
    return ctx.get(RECORD + args["record_id"])


def list_records(ctx: Context, args: dict[str, Any]) -> list[Any]:
    owner = args.get("owner_msp")
    out = [v for _, v in ctx.range(RECORD)]
    return [r for r in out if owner is None or r["owner_msp"] == owner]


def list_grants(ctx: Context, args: dict[str, Any]) -> list[Any]:
    out = [v for _, v in ctx.range(GRANT)]
    if owner := args.get("owner_msp"):
        out = [g for g in out if g["owner_msp"] == owner]
    if requester := args.get("requester_msp"):
        out = [g for g in out if g["requester_msp"] == requester]
    return out


def get_seal(ctx: Context, args: dict[str, Any]) -> Any:
    owner = args.get("owner_msp", ctx.caller_msp)
    return ctx.get(SEAL + bucket_key(owner, args["site"], args["record_type"], args["period"]))


def list_seals(ctx: Context, args: dict[str, Any]) -> list[Any]:
    out = [v for _, v in ctx.range(SEAL)]
    if owner := args.get("owner_msp"):
        out = [s for s in out if s["owner_msp"] == owner]
    return out


def list_receipts(ctx: Context, args: dict[str, Any]) -> list[Any]:
    out = [v for _, v in ctx.range(RECEIPT)]
    if record_id := args.get("record_id"):
        out = [r for r in out if r["record_id"] == record_id]
    return out


_ROUTES = {
    "commit_record": commit_record,
    "supersede_record": supersede_record,
    "open_seed_round": open_seed_round,
    "commit_seed_share": commit_seed_share,
    "reveal_seed_share": reveal_seed_share,
    "witness_requirement": witness_requirement_route,
    "seal_period": seal_period,
    "reopen_seal": reopen_seal,
    "amend_seal": amend_seal,
    "check_completeness": check_completeness,
    "report_falsification": report_falsification,
    "report_disclosure_mismatch": report_disclosure_mismatch,
    "get_finding": get_finding,
    "list_findings": list_findings,
    "get_seal": get_seal,
    "list_seals": list_seals,
    "grant_access": grant_access,
    "revoke_access": revoke_access,
    "record_verification": record_verification,
    "get_seed_round": get_seed_round,
    "get_record": get_record,
    "list_records": list_records,
    "list_grants": list_grants,
    "list_receipts": list_receipts,
}


def doccustody(ctx: Context, function: str, args: dict[str, Any]) -> Any:
    fn = _ROUTES.get(function)
    if fn is None:
        raise ChaincodeError(f"doccustody has no function {function}")
    return fn(ctx, args)
