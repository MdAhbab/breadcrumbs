"""
Period seals and completeness proofs.

The claim this router carries is the strongest one in the product and also the
easiest to overstate, so the endpoints are shaped to keep it honest. A seal
fixes *which records a period holds*. It does not attest that the records are
true, and it cannot see a document that was never committed at all. The
completeness response therefore always carries both counts and both roots, so
the interface can show the arithmetic rather than a verdict the user has to
take on trust.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from model.consortium import DOCUMENT_CHANNEL

from .. import ledger_service as ledger
from ..auth import CurrentUser, require_capability
from ..scoping import may_see_bucket, visible_buckets

router = APIRouter(tags=["seals"])


def now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class SealRequest(BaseModel):
    site: str
    record_type: str
    period: str
    record_ids: list[str] = Field(min_length=1)


class AmendRequest(BaseModel):
    added_record_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)


class CompletenessRequest(BaseModel):
    owner_msp: str
    site: str
    record_type: str
    period: str
    disclosed_record_ids: list[str]


def _fail(exc: ledger.LedgerError) -> HTTPException:
    denied = "may not" in exc.message or "does not own" in exc.message
    return HTTPException(
        status.HTTP_403_FORBIDDEN if denied else status.HTTP_400_BAD_REQUEST,
        {"message": exc.message, "code": exc.code},
    )


@router.get("/seals")
def list_seals(user: CurrentUser) -> list[dict]:
    """Seals over periods this caller may see."""
    require_capability(user, "read_seals")
    seals = ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_seals", {}, user.role)
    allowed = visible_buckets(user)
    if allowed is None:
        return seals
    return [s for s in seals if s["bucket"] in allowed]


@router.post("/seals", status_code=status.HTTP_201_CREATED)
def seal_period(body: SealRequest, user: CurrentUser) -> dict:
    """
    Close a period. The contract enumerates what the ledger holds and refuses if
    the declared list omits any of it — this layer does not pre-check that, on
    purpose, because a second copy of the rule is a rule that will drift.
    """
    require_capability(user, "write_seals")
    try:
        return ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "seal_period",
            {
                "site": body.site,
                "record_type": body.record_type,
                "period": body.period,
                "record_ids": body.record_ids,
                "timestamp": now(),
            },
            user.role,
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc


@router.post("/seals/{bucket}/amend")
def amend_seal(bucket: str, body: AmendRequest, user: CurrentUser) -> dict:
    """
    Add records to a closed period, permanently and visibly.

    The bucket arrives in the path as `owner|site|type|period`; its parts are
    handed to the contract, which re-derives the key from the caller's own MSP.
    A caller naming somebody else's bucket therefore cannot amend it — the
    identity in the key is never taken from the request.
    """
    require_capability(user, "write_seals")
    parts = bucket.split("|")
    if len(parts) != 4:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"code": "BAD_BUCKET", "message": "a bucket is owner|site|record_type|period"},
        )
    _, site, record_type, period = parts
    try:
        return ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "amend_seal",
            {
                "site": site,
                "record_type": record_type,
                "period": period,
                "added_record_ids": body.added_record_ids,
                "reason": body.reason,
                "timestamp": now(),
            },
            user.role,
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc


@router.post("/completeness")
def check_completeness(body: CompletenessRequest, user: CurrentUser) -> dict:
    """
    Was anything withheld?

    The response carries the sealed count, the disclosed count and both roots
    whether it passes or fails, because the interface's job here is to show the
    arithmetic. A bare boolean would be the same claim with the evidence
    removed.
    """
    require_capability(user, "read_seals")
    bucket = "|".join([body.owner_msp, body.site, body.record_type, body.period])
    if not may_see_bucket(user, bucket):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "code": "CAPABILITY_DENIED",
                "message": (
                    f"{user.label} holds no live grant against any record in {bucket}, "
                    "so it may not ask whether that period is complete."
                ),
            },
        )
    try:
        return ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "check_completeness",
            {
                "owner_msp": body.owner_msp,
                "site": body.site,
                "record_type": body.record_type,
                "period": body.period,
                "disclosed_record_ids": body.disclosed_record_ids,
            },
            user.role,
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc
