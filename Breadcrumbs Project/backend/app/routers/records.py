"""
Records, grants and verification — Plane A over HTTP.

The verification endpoint is the one that matters. It builds the Merkle proof
from the off-chain document, hands it to a verifier that recomputes the root
from the disclosure alone, and writes the receipt through chaincode — which
refuses if the grant does not cover the requested field. The scope check is the
contract's, not this file's.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from model.consortium import DOCUMENT_CHANNEL
from model.merkle import MerkleTree, verify_disclosure

from .. import ledger_service as ledger
from ..auth import CurrentUser, require_capability
from ..db import StoredDocument, get_session, notify

router = APIRouter(tags=["records"])


def now() -> str:
    """
    A real timestamp, in the format the chaincode compares against.

    Every write used to carry one hardcoded constant, so an entire demo's
    records shared a single commit time and the grant-expiry comparison was
    meaningless. The value still arrives at the contract as an argument — the
    contract itself must never read a clock, or two endorsers would disagree.
    """
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class CommitRequest(BaseModel):
    record_id: str
    record_type: str
    period: str
    site: str = "Gazipur"
    schema_version: str = "v2.1.0"
    rows: list[dict[str, Any]] = Field(min_length=1)


class GrantRequest(BaseModel):
    record_id: str
    requester_msp: str
    purpose_code: str
    field_name: str
    expires_at: str
    # Optional, and minted below when it is absent. Making the caller invent a
    # unique identifier for a ledger key is a footgun: the contract refuses a
    # duplicate, correctly, and the user sees a collision they had no way to
    # anticipate.
    grant_id: str | None = None


class VerifyRequest(BaseModel):
    grant_id: str
    record_id: str
    row_index: int = Field(ge=0)
    field_name: str
    receipt_id: str


def _fail(exc: ledger.LedgerError) -> HTTPException:
    code = (
        status.HTTP_403_FORBIDDEN
        if "does not own" in exc.message or "grant covers" in exc.message
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(code, {"message": exc.message, "code": exc.code})


@router.get("/records")
def list_records(user: CurrentUser) -> list[dict]:
    """
    Records this caller is entitled to see.

    A factory sees its own. A buyer or auditor sees only records it holds a live
    grant against — not every record on the channel, which is what an unscoped
    listing used to return.
    """
    require_capability(user, "read_records")
    records = ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_records", {}, user.role)

    if user.role == "factory":
        return [r for r in records if r["owner_msp"] == user.msp_id]
    if user.role in ("buyer", "auditor"):
        grants = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "list_grants",
            {"requester_msp": user.msp_id}, user.role,
        )
        granted = {g["record_id"] for g in grants if g["status"] == "active"}
        return [r for r in records if r["record_id"] in granted]
    return records


@router.get("/records/{record_id}")
def get_record(record_id: str, user: CurrentUser, db: Session = Depends(get_session)) -> dict:
    """
    One record, if this caller is entitled to it.

    Scoped through `scoped_records` rather than by fetching the record and
    hoping, because this endpoint was the one hole in an otherwise complete
    rule. `/api/records` filters the listing, `/screen` refuses a document you
    may not read, `/witness-requirement` and `/verify` both 404 and each has a
    test named after the rule — and this one served any record on the channel to
    any signed-in buyer that knew an identifier. The record page is exactly
    where someone would try a URL by hand.

    A record outside scope is a 404, not a 403, and that is the same choice the
    sibling endpoints make: "you may not see this record" and "there is no such
    record" have to be indistinguishable, or the refusal itself confirms the
    document exists.
    """
    require_capability(user, "read_records")
    from ..scoping import scoped_records

    record = next(
        (r for r in scoped_records(user) if r["record_id"] == record_id), None
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no record {record_id}")

    stored = db.get(StoredDocument, record_id)
    receipts = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "list_receipts",
        {"record_id": record_id}, user.role,
    )
    return {
        "record": record,
        "receipts": receipts,
        # Deliberately not the rows. The API never serves a document body; the
        # only way data leaves is one row at a time, through a proof.
        "rows_held_off_chain": len(stored.rows) if stored else 0,
    }


@router.post("/records", status_code=status.HTTP_201_CREATED)
def commit_record(
    body: CommitRequest, user: CurrentUser, db: Session = Depends(get_session)
) -> dict:
    """Hash the rows, commit the root, keep the body off-chain."""
    require_capability(user, "write_records")
    tree = MerkleTree(body.rows)
    try:
        result = ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_record",
            {
                "record_id": body.record_id, "merkle_root": tree.root,
                "record_type": body.record_type, "period": body.period,
                "site": body.site, "row_count": len(body.rows),
                "schema_version": body.schema_version, "timestamp": now(),
            },
            role=user.role, timestamp=now(),
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc

    db.merge(
        StoredDocument(
            record_id=body.record_id, owner_msp=user.msp_id, record_type=body.record_type,
            period=body.period, site=body.site, schema_version=body.schema_version,
            merkle_root=tree.root, rows=body.rows, salts=tree.salts, committed_at=now(),
        )
    )
    db.commit()
    return {
        "record_id": body.record_id,
        "merkle_root": tree.root,
        "row_count": len(body.rows),
        "tx_id": result["tx_id"],
        "block": result["block"],
    }


@router.post("/records/{record_id}/screen")
def screen_record(
    record_id: str, user: CurrentUser, db: Session = Depends(get_session)
) -> dict:
    """
    Run the detector over one committed record.

    This is the only place in the product where the model is actually executed.
    Everything else about the learning plane is governance — which benchmark was
    sealed, who signed what, whether the gate promoted it — and none of that
    scores a document.

    Scoped exactly like reading the record, and for the same reason: a score is
    a statement about a document's contents, so being able to obtain one for a
    document you may not read would be a disclosure with extra steps.

    The response is deliberately not just a number. It carries the threshold,
    the measured false-positive rate at that threshold, and a sentence saying
    what the score is not, because a bare probability beside a cryptographic
    proof invites a reader to treat the two as the same kind of fact. They are
    not: the proof is checkable and the score is an opinion.
    """
    require_capability(user, "read_records")
    from .. import detector
    from ..scoping import scoped_records

    if not any(r["record_id"] == record_id for r in scoped_records(user)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no record {record_id}")

    stored = db.get(StoredDocument, record_id)
    if stored is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {
                "code": "NO_BODY",
                "message": (
                    f"{record_id} is committed on the ledger but its rows are not in "
                    "this store. The detector reads the document, so there is nothing "
                    "for it to score."
                ),
            },
        )

    return {
        "record_id": record_id,
        **detector.screen(stored.record_type, stored.rows),
    }


@router.get("/grants")
def list_grants(user: CurrentUser) -> list[dict]:
    """
    Grants, from whichever end the caller stands at.

    A buyer or auditor sees what it holds; a factory sees what it has issued.
    The consortium sees the channel, and that is not a widening of scope: a grant
    is on-chain metadata naming two organisations, a purpose code and a field
    name, with no personal data in it, and the consortium is a member of the
    channel it is written on. Filtering the consortium by `owner_msp` returned
    nothing — BGMEA owns no records — which made the network view state that
    every member held no grants at all. An empty list is a claim, and that one
    was false.
    """
    require_capability(user, "read_grants")
    if user.role == "consortium":
        args: dict[str, str] = {}
    elif user.role in ("buyer", "auditor"):
        args = {"requester_msp": user.msp_id}
    else:
        args = {"owner_msp": user.msp_id}
    return ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_grants", args, user.role)


@router.post("/grants", status_code=status.HTTP_201_CREATED)
def grant_access(
    body: GrantRequest, user: CurrentUser, db: Session = Depends(get_session)
) -> dict:
    """
    Disclose one field of one record to one organisation, directly.

    The other way in is answering a buyer's request, which is the usual path.
    This is the one a factory needs when it is looking at a period it has
    already sealed and can see a record it never released — there is no request
    to answer there, and without this the shortfall was visible and not
    actionable.
    """
    require_capability(user, "write_grants")
    args = body.model_dump()
    args["grant_id"] = body.grant_id or _next_grant_id(user)
    try:
        result = ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "grant_access",
            {**args, "timestamp": now()}, role=user.role, timestamp=now(),
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc

    notify(
        db,
        body.requester_msp,
        "access_granted",
        f"{user.org} disclosed {body.field_name} on {body.record_id} to you "
        f"until {body.expires_at[:10]}",
    )
    db.commit()
    return result


def _next_grant_id(user) -> str:
    """
    The next free `g-NNNN`, continuing the scheme the world was seeded with.

    Derived from what is on the chain rather than from a counter somebody has to
    remember to keep, so it stays correct across a restart that rebuilds the
    ledger.
    """
    existing = {
        g["grant_id"]
        for g in ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "list_grants", {}, user.role
        ) or []
    }
    n = len(existing) + 1
    while f"g-{n:04d}" in existing:
        n += 1
    return f"g-{n:04d}"


@router.post("/grants/{grant_id}/revoke")
def revoke_access(
    grant_id: str, reason: str, user: CurrentUser, db: Session = Depends(get_session)
) -> dict:
    """
    End a grant, permanently, with the reason on the chain.

    The reason is required and is not decoration: it is written into the grant,
    it is shown to the organisation whose access it ends, and it cannot be
    edited afterwards. The interface used to send a fixed string naming the
    screen the button was on, which records where it was done rather than why.

    Revocation is not reversible, by design — see the contract. Access can be
    granted again, and that is a new grant with its own identifier, visible as
    a new grant rather than as the old one quietly coming back.
    """
    require_capability(user, "write_grants")
    if not reason.strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {
                "code": "NO_REASON",
                "message": (
                    "Say why. The reason goes on the ledger with your identity and "
                    "is shown to the organisation whose access this ends."
                ),
            },
        )
    grants = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "list_grants", {"owner_msp": user.msp_id}, user.role
    )
    grant = next((g for g in grants if g["grant_id"] == grant_id), None)
    try:
        result = ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "revoke_access",
            {"grant_id": grant_id, "reason": reason.strip(), "timestamp": now()},
            role=user.role, timestamp=now(),
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc

    if grant is not None:
        notify(
            db,
            grant["requester_msp"],
            "grant_revoked",
            f"{user.org} withdrew your access to {grant['field_name']} on "
            f"{grant['record_id']} — {reason.strip()}",
        )
        db.commit()
    return result


@router.post("/verify")
def verify_one_row(
    body: VerifyRequest, user: CurrentUser, db: Session = Depends(get_session)
) -> dict:
    """
    Prove one row against the committed root.

    Everything a verifier needs is in the response and nothing else is: the
    disclosed value, its salt, the sibling hashes, and the root already on the
    ledger. The other rows are not sent and cannot be recovered from what is.
    """
    require_capability(user, "verify_records")
    stored = db.get(StoredDocument, body.record_id)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no record {body.record_id}")
    if body.row_index >= len(stored.rows):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"row {body.row_index} is outside this record's {len(stored.rows)} rows",
        )

    tree = MerkleTree(stored.rows, stored.salts)
    disclosure = tree.prove(body.row_index, body.record_id, body.field_name)
    ok, computed, trace = verify_disclosure(disclosure, stored.merkle_root)

    # The contract decides whether this verification was in scope.
    try:
        receipt = ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "record_verification",
            {
                "receipt_id": body.receipt_id, "grant_id": body.grant_id,
                "field_name": body.field_name, "result": "match" if ok else "no_match",
                "computed_root": computed, "timestamp": now(),
            },
            role=user.role, timestamp=now(),
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc

    return {
        "verified": ok,
        "verdict": "Verified — record is genuine" if ok else "Proof failed — do not rely on this record",
        "disclosed": {
            "field_name": body.field_name,
            "value": disclosure.value.get(body.field_name, disclosure.value),
        },
        "proof": {
            "computed_root": computed,
            "on_chain_root": stored.merkle_root,
            "match": ok,
            "steps": [s.to_dict() for s in disclosure.path],
            "ladder": trace,
            "rows_in_record": len(stored.rows),
            "rows_disclosed": 1,
        },
        "receipt": receipt["response"],
        "tx_id": receipt["tx_id"],
        "block": receipt["block"],
    }
