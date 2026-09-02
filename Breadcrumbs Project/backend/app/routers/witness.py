"""
Attesting witnesses, and the seed round that assigns them.

The assignment must not be choosable, or a factory picks a friendly witness and
the counter-signature means nothing. It comes from a commit-reveal round run by
the consortium, and until such a round closes the rule is simply not in force.
Every response here carries `in_force` for that reason: a screen that hides the
distinction implies a guarantee the ledger is not making.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from model.consortium import DOCUMENT_CHANNEL

from .. import ledger_service as ledger
from ..auth import CurrentUser, require_capability
from ..scoping import scoped_records

router = APIRouter(tags=["witness"])


def now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class SeedRoundRequest(BaseModel):
    round_id: str
    members: list[str] = Field(min_length=2)
    sample_percent: int = Field(ge=0, le=100)
    quorum: int | None = None


class CommitShareRequest(BaseModel):
    commitment: str = Field(min_length=64, max_length=64)


class RevealShareRequest(BaseModel):
    share: str = Field(min_length=1)


def _fail(exc: ledger.LedgerError) -> HTTPException:
    denied = "only the consortium" in exc.message or "is not in this round" in exc.message
    return HTTPException(
        status.HTTP_403_FORBIDDEN if denied else status.HTTP_400_BAD_REQUEST,
        {"message": exc.message, "code": exc.code},
    )


@router.get("/records/{record_id}/witness-requirement")
def witness_requirement(record_id: str, user: CurrentUser) -> dict:
    """
    Who was assigned to counter-sign this record, and what did they claim to
    have checked?

    Scoped like the record itself: asking about a document you cannot see would
    leak that it exists, and its owner, and its type.
    """
    require_capability(user, "read_witness")
    record = next((r for r in scoped_records(user) if r["record_id"] == record_id), None)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no record {record_id}")

    requirement = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "witness_requirement",
        {
            "record_id": record_id,
            "record_type": record["record_type"],
            "owner_msp": record["owner_msp"],
        },
        user.role,
    )
    # `witness_requirement` answers for the round that is active *now*, because
    # the contract has no historical view of its own rounds. A record committed
    # before the consortium adopted the rule therefore comes back as "required"
    # with no attestations, which reads on screen as an assigned witness having
    # refused to sign. It is not: nothing was required of it. The comparison
    # below is what lets the interface tell those two apart.
    round_opened_at = ""
    if requirement.get("round_id"):
        rnd = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "get_seed_round",
            {"round_id": requirement["round_id"]}, user.role,
        )
        round_opened_at = (rnd or {}).get("opened_at", "")

    committed_at = record.get("committed_at", "")
    return {
        **requirement,
        # What was actually collected at capture, as against what was required.
        # The gap between the two is the interesting part and the UI shows it.
        "attestations": record.get("attestations", []),
        "attested_by": record.get("witnesses", []),
        "committed_at": committed_at,
        "round_opened_at": round_opened_at,
        "predates_rule": bool(
            round_opened_at and committed_at and committed_at < round_opened_at
        ),
    }


@router.get("/witness/requirement")
def planned_requirement(
    record_id: str, record_type: str, user: CurrentUser
) -> dict:
    """
    Who *would* be assigned to counter-sign a record that does not exist yet.

    The contract exposes this deliberately — "callable before committing, so a
    factory can find out who to ask rather than guess" — and the interface needs
    it for the same reason. Without it, sealing a witnessed record type is a
    button that fails with a refusal the user could not have anticipated.

    The owner is the caller's own MSP and is not taken from the request: asking
    who would witness somebody else's record would leak the assignment for a
    document that caller has nothing to do with.
    """
    require_capability(user, "read_witness")
    return ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "witness_requirement",
        {
            "record_id": record_id,
            "record_type": record_type,
            "owner_msp": user.msp_id,
        },
        user.role,
    )


@router.get("/seed-rounds/{round_id}")
def get_seed_round(round_id: str, user: CurrentUser) -> dict:
    require_capability(user, "read_witness")
    rnd = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "get_seed_round", {"round_id": round_id}, user.role
    )
    if rnd is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no seed round {round_id}")
    # The shares are the secret half of a commit-reveal; publishing them before
    # the round closes would let a late member grind its own share.
    if rnd["status"] != "closed":
        rnd = {**rnd, "shares": {}, "seed": None}
    return rnd


@router.post("/seed-rounds", status_code=status.HTTP_201_CREATED)
def open_seed_round(body: SeedRoundRequest, user: CurrentUser) -> dict:
    require_capability(user, "write_seed_rounds")
    args = {
        "round_id": body.round_id,
        "members": body.members,
        "sample_percent": body.sample_percent,
        "timestamp": now(),
    }
    if body.quorum is not None:
        args["quorum"] = body.quorum
    try:
        return ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "open_seed_round", args, user.role
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc


@router.post("/seed-rounds/{round_id}/commit")
def commit_share(round_id: str, body: CommitShareRequest, user: CurrentUser) -> dict:
    """Publish the hash of your share, before anybody has revealed theirs."""
    require_capability(user, "contribute_seed")
    try:
        return ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_seed_share",
            {"round_id": round_id, "commitment": body.commitment, "timestamp": now()},
            user.role,
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc


@router.post("/seed-rounds/{round_id}/reveal")
def reveal_share(round_id: str, body: RevealShareRequest, user: CurrentUser) -> dict:
    """Reveal it. The contract checks it against what you committed."""
    require_capability(user, "contribute_seed")
    try:
        return ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "reveal_seed_share",
            {"round_id": round_id, "share": body.share, "timestamp": now()},
            user.role,
        )
    except ledger.LedgerError as exc:
        raise _fail(exc) from exc
