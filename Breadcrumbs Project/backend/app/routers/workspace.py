"""
The aggregates each dashboard is actually built around.

Every screen in this product used to assemble its own view out of a fixture
file. These endpoints replace those fixtures with the same information derived
from the chain and the corpus, and they are grouped here rather than scattered
because they share one property: none of them is a new source of truth. The
activity feed is the block log read back as sentences, the auditor's queue is
its own live grants, the directory is the channel configuration. If any of them
disagrees with the ledger, this file is wrong.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from model.consortium import DOCUMENT_CHANNEL, MODEL_CHANNEL, ORGS

from .. import corpus
from .. import ledger_service as ledger
from ..auth import CurrentUser, require_capability
from ..db import Attestation, BuyerRequest, get_session, notify
from ..scoping import scoped_records

router = APIRouter(tags=["workspace"])

# The organisations the interface names, with the joining dates the consortium
# was built with. `ORGS` is the same tuple the network's MSP is configured from,
# so a member cannot appear on screen without being on the network.
ORG_KIND_LABEL = {
    "factory": "Factory",
    "buyer": "Buyer / Brand",
    "auditor": "Auditor",
    "consortium": "Consortium",
    "regulator": "Regulator",
}

COUNTRY_NAME = {"BD": "Bangladesh", "IE": "Ireland", "FR": "France"}


@router.get("/orgs")
def directory(user: CurrentUser) -> list[dict]:
    """
    Who is on the network, and on which channels.

    Available to every signed-in role including the regulator: membership is a
    governance fact, not factory data, and an observer that cannot see who the
    members are cannot observe anything useful.
    """
    require_capability(user, "read_directory")
    network = ledger.consortium().network
    channels = {
        name: channel.config.get("members", [])
        for name, channel in network.channels.items()
    }
    return [
        {
            "msp_id": msp_id,
            "name": name,
            "kind": kind,
            "kind_label": ORG_KIND_LABEL.get(kind, kind),
            "country": COUNTRY_NAME.get(country, country),
            "channels": sorted(c for c, members in channels.items() if msp_id in members),
            "is_you": msp_id == user.msp_id,
        }
        for msp_id, name, kind, country in ORGS
    ]


# What each chaincode function did, in a sentence rather than a function name.
# The interface used to hold this vocabulary; it belongs next to the log it
# describes, so a new contract function shows up as an unlabelled event here
# rather than being silently dropped by a frontend switch statement.
FUNCTION_KIND: dict[str, tuple[str, str]] = {
    "commit_record": ("seal", "committed"),
    "supersede_record": ("seal", "superseded"),
    "seal_period": ("seal", "sealed a period"),
    "reopen_seal": ("revoke", "reopened a sealed period"),
    "amend_seal": ("seal", "amended a seal"),
    "grant_access": ("grant", "granted access"),
    "revoke_access": ("revoke", "revoked access"),
    "record_verification": ("verify", "verified a disclosure"),
    "open_seed_round": ("request", "opened a witness seed round"),
    "commit_seed_share": ("request", "committed a seed share"),
    "reveal_seed_share": ("request", "revealed a seed share"),
    "install_group": ("seal", "installed accumulator parameters"),
    "advance_epoch": ("seal", "folded an epoch"),
    "publish_beacon": ("seal", "published a delay proof"),
    "commit_benchmark": ("request", "sealed a benchmark"),
    "open_round": ("request", "opened a training round"),
    "evaluate_gate": ("verify", "ran the Continuity Gate"),
}


@router.get("/activity")
def activity(user: CurrentUser, limit: int = 40) -> list[dict]:
    """
    What has happened, read out of the blocks themselves.

    This is the factory's shift log and the consortium's event stream. It is not
    a second store that something has to remember to write to — it is the chain,
    which is the only record that cannot be quietly edited to make the feed look
    better than the history.

    Scoped by submitter: a caller sees the transactions its own organisation
    submitted, plus the ones naming it. The consortium sees the channel.
    """
    require_capability(user, "read_activity")
    out: list[dict[str, Any]] = []
    for channel in (DOCUMENT_CHANNEL, MODEL_CHANNEL):
        try:
            blocks = ledger.blocks(channel, limit=400)
        except KeyError:
            continue
        for block in blocks:
            for tx in block["transactions"]:
                submitter_msp = tx["submitter"].split("::")[0]
                if user.role != "consortium" and submitter_msp != user.msp_id:
                    continue
                kind, phrase = FUNCTION_KIND.get(tx["function"], ("request", tx["function"]))
                out.append(
                    {
                        "at": block["timestamp"],
                        "kind": kind,
                        "text": f"{submitter_msp.replace('MSP', '')} {phrase}",
                        "function": tx["function"],
                        "chaincode": tx["chaincode"],
                        "channel": channel,
                        "block": block["number"],
                        "tx_id": tx["tx_id"],
                        "valid": tx["valid"],
                    }
                )
    out.sort(key=lambda e: (e["at"], e["block"]), reverse=True)
    return out[:limit]


@router.get("/audit/queue")
def audit_queue(user: CurrentUser, db: Session = Depends(get_session)) -> dict:
    """
    The auditor's bench: every record it holds a live grant against.

    "Queued" and "verified" are not stored anywhere — they are read from whether
    a verification receipt exists on the chain for that grant. A separate status
    column would be a second truth that could drift from the receipts, and the
    receipts are the part a third party can check.
    """
    require_capability(user, "read_queue")
    grants = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "list_grants",
        {"requester_msp": user.msp_id}, user.role,
    )
    receipts = ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_receipts", {}, user.role)
    verified = {r["grant_id"]: r for r in receipts or []}
    records = {r["record_id"]: r for r in scoped_records(user)}

    items = []
    for grant in grants:
        record = records.get(grant["record_id"])
        if record is None:
            continue
        receipt = verified.get(grant["grant_id"])
        items.append(
            {
                "grant_id": grant["grant_id"],
                "record_id": grant["record_id"],
                "owner_msp": record["owner_msp"],
                "record_type": record["record_type"],
                "period": record["period"],
                "site": record["site"],
                "row_count": record["row_count"],
                "field_name": grant["field_name"],
                "purpose_code": grant["purpose_code"],
                "grant_status": grant["status"],
                "state": (
                    "revoked" if grant["status"] != "active"
                    else "passed" if receipt and receipt["result"] == "match"
                    else "failed" if receipt
                    else "queued"
                ),
                "receipt_id": receipt["receipt_id"] if receipt else None,
                "verified_at": receipt["verified_at"] if receipt else None,
            }
        )
    items.sort(key=lambda i: (i["state"] != "queued", i["record_id"]))
    return {
        "items": items,
        "attestations": [
            {
                "id": a.id, "claim_code": a.claim_code, "evidence_scope": a.evidence_scope,
                "statement": a.statement, "status": a.status, "signed_at": a.signed_at,
                "auditor_name": a.auditor_name,
            }
            for a in db.query(Attestation).filter(Attestation.auditor_msp == user.msp_id).all()
        ],
    }


@router.get("/about")
def about() -> dict:
    """
    What this system is, where its data came from, and what it does not do.

    Unauthenticated on purpose: it is what the landing page is made of, and a
    claim about a system's honesty that you have to sign in to read is not much
    of a claim. The limitations are quoted from the report and are served from
    here so that one edit changes them everywhere rather than the interface
    keeping a friendlier copy.
    """
    return {
        "provenance": {**corpus.provenance(), **ledger_counts()},
        # Two real gate decisions, so the public explainer demonstrates the
        # mechanism rather than illustrating it. These are consortium-level facts
        # about a shared model and name no factory document, which is why they can
        # be served without a token when a record never could.
        "gate": _headline_decisions(),
        "windows": [
            {"site": site, "period": period, "reason": reason}
            for site, period, reason in corpus.WINDOWS
        ],
        "limitations": LIMITATIONS,
        "comparison": COMPARISON,
    }


LIMITATIONS = [
    "Every result is a simulation on invented data. Not a measurement of any factory.",
    "Our own benchmark cannot validate the learning claim — a model trained on "
    "summaries alone matched the full system.",
    "We removed one of our own mechanisms after measuring that it cost 3.9 points "
    "of accuracy.",
    "We chose the difficulty setting, and it sits near the value that makes the "
    "baseline look worst.",
    "Our added noise is not differential privacy. No sensitivity bound, no budget, "
    "and released variances carry no noise at all.",
    "The simulation omits every privacy and robustness component the design "
    "specifies, so the reported accuracy is an upper bound.",
    "Secure aggregation, robust averaging and contribution scoring cannot all three "
    "hold. We gave up the first.",
    "A signed record of a false statement is still a correct record of a lie. The "
    "first-mile problem is mitigated, not solved.",
    "Infrastructure is costed from published list prices, and the audit saving "
    "depends on buyers accepting cryptographic evidence.",
]

COMPARISON = {
    "columns": [
        "Ledger", "Internal records", "Shared model", "Learns over time",
        "Gate on past tasks",
    ],
    "rows": [
        {"name": "TextileGenesis / TrusTrace", "cells": [True, False, False, False, False]},
        {"name": "AWARE & DigiProd Pass (BGMEA)", "cells": [True, False, False, False, False]},
        {"name": "Guardtime & OpenTimestamps", "cells": [True, True, False, False, False]},
        {"name": "Swarm Learning", "cells": [True, False, True, False, False]},
        {"name": "LiFeChain", "cells": [True, False, True, True, False]},
        {"name": "Breadcrumbs", "cells": [True, True, True, True, True]},
    ],
}


# --------------------------------------------------------------------------
# the request that becomes a grant
# --------------------------------------------------------------------------
class NewRequest(BaseModel):
    """What a buyer asks for. One field, one purpose, one period."""

    supplier_msp: str
    record_type: str
    period: str
    purpose_code: str = Field(min_length=3)
    field_name: str = Field(min_length=1)
    item_reference: str | None = None
    expires_at: str


class Decision(BaseModel):
    record_id: str | None = None
    reason: str | None = None


def _now() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _grants_by_id(user) -> dict[str, dict]:
    """Every grant this caller can see, keyed by identifier."""
    if user.role in ("buyer", "auditor"):
        args = {"requester_msp": user.msp_id}
    elif user.role == "factory":
        args = {"owner_msp": user.msp_id}
    else:
        args = {}
    grants = ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_grants", args, user.role)
    return {g["grant_id"]: g for g in grants or []}


@router.get("/requests")
def list_requests(user: CurrentUser, db: Session = Depends(get_session)) -> list[dict]:
    """
    Requests, from whichever end the caller stands at.

    A buyer sees what it asked for; a factory sees what it has been asked. This
    lives off-chain on purpose: an unanswered question is not a fact about the
    world and does not belong in an append-only record. Only the answer does,
    and the answer is a grant.

    Which is exactly why `status` alone was not enough. It is a stored copy of a
    decision, and the grant that decision produced lives on the ledger, where it
    can be revoked through an endpoint that has never heard of this row. So a
    request whose access had been withdrawn went on reporting "granted" to the
    buyer it had been withdrawn from. The stored status stays what the factory
    decided; `grant_status` is read off the chain every time, because the chain
    is the authority on whether the access is still live.
    """
    require_capability(user, "read_requests")
    query = db.query(BuyerRequest)
    query = (
        query.filter(BuyerRequest.requester_msp == user.msp_id)
        if user.role in ("buyer", "auditor")
        else query.filter(BuyerRequest.supplier_msp == user.msp_id)
        if user.role == "factory"
        else query
    )
    rows = query.order_by(BuyerRequest.requested_at.desc()).all()
    grants = _grants_by_id(user) if any(r.grant_id for r in rows) else {}
    out = []
    for r in rows:
        grant = grants.get(r.grant_id) if r.grant_id else None
        out.append(
            {
                "id": r.id, "requester_msp": r.requester_msp, "supplier_msp": r.supplier_msp,
                "record_type": r.record_type, "period": r.period,
                "item_reference": r.item_reference, "purpose_code": r.purpose_code,
                "field_name": r.field_name, "expires_at": r.expires_at,
                "status": r.status, "grant_id": r.grant_id, "requested_at": r.requested_at,
                "decline_reason": r.decline_reason,
                "grant_status": grant["status"] if grant else None,
                "grant_record_id": grant["record_id"] if grant else None,
                "grant_revoked_reason": grant.get("revoked_reason") if grant else None,
            }
        )
    return out


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def make_request(
    body: NewRequest, user: CurrentUser, db: Session = Depends(get_session)
) -> dict:
    require_capability(user, "write_requests")
    count = db.query(BuyerRequest).count()
    row = BuyerRequest(
        id=f"br-{count + 1:03d}", requester_msp=user.msp_id,
        supplier_msp=body.supplier_msp, record_type=body.record_type,
        period=body.period, item_reference=body.item_reference,
        purpose_code=body.purpose_code, field_name=body.field_name,
        expires_at=body.expires_at, status="pending", requested_at=_now(),
    )
    db.add(row)
    notify(
        db,
        body.supplier_msp,
        "access_request",
        f"{user.org} asked for {body.field_name} from "
        f"{body.record_type.replace('_', ' ')}, {body.period} — {body.purpose_code}",
    )
    db.commit()
    return {"id": row.id, "status": row.status}


@router.post("/requests/{request_id}/grant")
def answer_request(
    request_id: str, body: Decision, user: CurrentUser,
    db: Session = Depends(get_session),
) -> dict:
    """
    Answer a request by writing the grant on chain.

    The record has to be named here because a request is asked in general terms
    — "payroll, May, that site" — and a grant is specific. The contract still
    decides whether this caller may grant against that record; nothing is
    pre-authorised by the request existing.

    A request can be answered more than once, and that is the whole point of the
    version suffix below. Revocation is permanent and stays on the chain with
    its reason; what a factory needs after revoking in error is not an undo but
    the ability to grant the access *again*, visibly, as a new grant. Deriving
    the identifier from the request alone made that impossible — the second
    grant collided with the first and the contract refused it — so a single
    misclick ended a buyer's request for good.

    What is still refused is granting on top of a live grant. That is not a
    recovery, it is a duplicate, and the message says which.
    """
    require_capability(user, "write_grants")
    row = db.get(BuyerRequest, request_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no request {request_id}")
    if row.supplier_msp != user.msp_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "this request was not addressed to you"
        )

    issued = _grants_by_id(user)
    live = issued.get(row.grant_id) if row.grant_id else None
    if live is not None and live["status"] == "active":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "GRANT_IS_LIVE",
                "message": (
                    f"{row.grant_id} is still active. Revoke it before issuing "
                    "access again, so there is never more than one live grant "
                    "answering the same request."
                ),
            },
        )
    if row.status == "declined" and live is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "REQUEST_DECLINED",
                "message": (
                    "This request was declined. Reconsider it first — that puts it "
                    "back in front of you as a decision rather than answering one "
                    "you have already refused."
                ),
            },
        )
    if not body.record_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "name the record this grant covers; a request names a period, a grant "
            "names a document",
        )

    # One grant per attempt, numbered. The first keeps the plain identifier so
    # nothing that already refers to it has to change.
    stem = f"g-{row.id}"
    previous = [k for k in issued if k == stem or k.startswith(f"{stem}-r")]
    grant_id = stem if not previous else f"{stem}-r{len(previous) + 1}"

    try:
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "grant_access",
            {
                "grant_id": grant_id, "record_id": body.record_id,
                "requester_msp": row.requester_msp, "purpose_code": row.purpose_code,
                "field_name": row.field_name, "expires_at": row.expires_at,
                "timestamp": _now(),
            },
            role=user.role, timestamp=_now(),
        )
    except ledger.LedgerError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, {"code": exc.code, "message": exc.message}
        ) from exc

    reissued = bool(previous)
    row.status = "granted"
    row.grant_id = grant_id
    row.decline_reason = None
    notify(
        db,
        row.requester_msp,
        "access_granted",
        f"{user.org} {'re-issued' if reissued else 'granted'} access to "
        f"{row.field_name} on {body.record_id} until {row.expires_at[:10]}",
    )
    db.commit()
    return {
        "id": row.id, "status": row.status, "grant_id": grant_id, "reissued": reissued,
    }


@router.post("/requests/{request_id}/decline")
def decline_request(
    request_id: str, body: Decision, user: CurrentUser,
    db: Session = Depends(get_session),
) -> dict:
    """
    Refuse a request, and say why.

    The reason used to be accepted, parsed and dropped, so the buyer learned
    that it had been refused and nothing else. A refusal a counterparty cannot
    understand is one it will simply send again.
    """
    require_capability(user, "write_grants")
    row = db.get(BuyerRequest, request_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no request {request_id}")
    if row.supplier_msp != user.msp_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "this request was not addressed to you"
        )
    # A request cannot be refused while the grant answering it is still live.
    # Nothing stopped that before, and it produced a row saying "declined" over
    # access the buyer could still use — the same disagreement between the store
    # and the chain that `list_requests` exists to prevent, in the other
    # direction. Ending access is revocation, and revocation is on the ledger.
    live = _grants_by_id(user).get(row.grant_id) if row.grant_id else None
    if live is not None and live["status"] == "active":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "GRANT_IS_LIVE",
                "message": (
                    f"{row.grant_id} answers this request and is still active. "
                    "Revoke the grant — declining the request would not end the "
                    "access it already produced."
                ),
            },
        )
    row.status = "declined"
    row.decline_reason = (body.reason or "").strip() or None
    notify(
        db,
        row.requester_msp,
        "access_declined",
        f"{user.org} declined your request for {row.field_name}, {row.period}"
        + (f" — {row.decline_reason}" if row.decline_reason else ""),
    )
    db.commit()
    return {"id": row.id, "status": row.status, "reason": row.decline_reason}


@router.post("/requests/{request_id}/reconsider")
def reconsider_request(
    request_id: str, user: CurrentUser, db: Session = Depends(get_session)
) -> dict:
    """
    Put a declined request back in front of the factory as an open decision.

    A decline was terminal: the status went to "declined" and every other
    handler requires "pending", so one misclick ended a buyer's request with no
    recourse at either end. This is the way back, and it is deliberately not on
    the ledger. The module's own rule applies — an unanswered question is not a
    fact about the world, and a question that has been re-opened is still an
    unanswered question. What the ledger records is grants, and no grant is
    written or erased here.
    """
    require_capability(user, "write_grants")
    row = db.get(BuyerRequest, request_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no request {request_id}")
    if row.supplier_msp != user.msp_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "this request was not addressed to you"
        )
    if row.status != "declined":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "NOT_DECLINED",
                "message": (
                    f"This request is {row.status}. Only a declined request can be "
                    "reconsidered."
                ),
            },
        )
    row.status = "pending"
    row.decline_reason = None
    notify(
        db,
        row.requester_msp,
        "access_request",
        f"{user.org} reopened your request for {row.field_name}, {row.period}",
    )
    db.commit()
    return {"id": row.id, "status": row.status}


class NewAttestation(BaseModel):
    """An auditor's signed statement over a batch it has actually verified."""

    claim_code: str = Field(min_length=3)
    evidence_scope: str = Field(min_length=3)
    statement: str = Field(min_length=12)


@router.post("/attestations", status_code=status.HTTP_201_CREATED)
def sign_attestation(
    body: NewAttestation, user: CurrentUser, db: Session = Depends(get_session)
) -> dict:
    """
    Record an attestation, and refuse one the evidence does not support.

    The check is the point: an auditor may not attest to a batch it has not
    finished verifying. The API counts the receipts on the chain rather than
    trusting a flag the client sends, because the client is the thing being
    checked. This is an off-chain professional statement, not a ledger fact —
    what is on the ledger is each verification receipt underneath it.
    """
    require_capability(user, "write_attestations")

    grants = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "list_grants",
        {"requester_msp": user.msp_id}, user.role,
    )
    live = {g["grant_id"] for g in grants if g["status"] == "active"}
    receipts = ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_receipts", {}, user.role)
    checked = {r["grant_id"] for r in receipts or []}
    outstanding = sorted(live - checked)
    if outstanding:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {
                "code": "BATCH_INCOMPLETE",
                "message": (
                    f"{len(outstanding)} record(s) in your batch have no verification "
                    "receipt on the ledger. An attestation has to rest on evidence "
                    "that exists."
                ),
            },
        )

    count = db.query(Attestation).count()
    row = Attestation(
        id=f"at-{count + 1:03d}", auditor_msp=user.msp_id, auditor_name=user.person,
        claim_code=body.claim_code, evidence_scope=body.evidence_scope,
        statement=body.statement, status="verified", signed_at=_now(),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "status": row.status, "signed_at": row.signed_at}


@router.get("/receipts/{receipt_id}")
def public_receipt(receipt_id: str) -> dict:
    """
    A verification receipt, checkable by anyone holding its identifier.

    Unauthenticated on purpose. The claim the product makes is that a buyer can
    hand a receipt to a third party and that party can check it without an
    account and without asking the factory for anything — and a receipt endpoint
    behind a login would make that claim false.

    What comes back is the receipt, the record's committed root, and whether the
    two agree. What does *not* come back is the disclosed value. That was
    released to the grantee under a grant covering one field; publishing it here
    because somebody knows a receipt id would undo the whole disclosure model.
    The receipt proves that a verification happened and that the root matched.
    Seeing the figure requires being the party it was disclosed to.
    """
    receipts = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "list_receipts", {}, "consortium"
    )
    receipt = next(
        (r for r in receipts or [] if r["receipt_id"] == receipt_id), None
    )
    if receipt is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            {
                "code": "NO_RECEIPT",
                "message": (
                    f"No verification receipt {receipt_id} is on this ledger. A receipt "
                    "identifier is issued when a disclosure is proved."
                ),
            },
        )

    record = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "get_record",
        {"record_id": receipt["record_id"]}, "consortium",
    )
    on_chain_root = record["merkle_root"] if record else None
    return {
        "receipt": receipt,
        "record": (
            {
                "record_id": record["record_id"],
                "record_type": record["record_type"],
                "period": record["period"],
                "site": record["site"],
                "owner_msp": record["owner_msp"],
                "row_count": record["row_count"],
                "committed_at": record["committed_at"],
                "status": record["status"],
            }
            if record else None
        ),
        "on_chain_root": on_chain_root,
        "root_matches": on_chain_root is not None
        and receipt["computed_root"] == on_chain_root,
        "note": (
            "This receipt records that a disclosure was proved against the root the "
            "owner committed. The disclosed value is not published here: it was "
            "released under a grant covering one field, to one counterparty."
        ),
    }


def _headline_decisions() -> dict[str, Any]:
    """The most recent promotion and the most recent refusal, whichever they are."""
    try:
        models = ledger.query(MODEL_CHANNEL, "fedmodel", "list_models", {}, "consortium")
    except Exception:  # noqa: BLE001 - an empty model channel is not an error here
        return {"promoted": None, "rejected": None}

    def newest(status: str) -> dict | None:
        matching = sorted(
            (m for m in models or [] if m["status"] == status),
            key=lambda m: m["decided_at"],
            reverse=True,
        )
        if not matching:
            return None
        return ledger.query(
            MODEL_CHANNEL, "fedmodel", "get_decision",
            {"candidate_id": matching[0]["model_id"]}, "consortium",
        )

    # A promoted candidate that was later superseded is still a promotion, and on
    # a channel where everything has been superseded it is the only one there is.
    return {
        "promoted": newest("promoted") or newest("superseded"),
        "rejected": newest("rejected"),
    }


def ledger_counts() -> dict[str, Any]:
    """
    How much of the corpus actually reached the chain, and what did not.

    Shared by `/api/about` and `/api/health` so the two cannot disagree about
    how large the world is — the landing page was printing "runs on  documents"
    because only one of them carried the count.
    """
    from ..seed import LAST_RUN

    try:
        records = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "list_records", {}, "factory"
        )
    except Exception:  # noqa: BLE001 - before the world is built there is no chain
        records = []
    return {
        "records_on_ledger": len(records),
        "excluded_by_schema": int(LAST_RUN.get("excluded_by_schema", 0)),
        "excluded_reason": LAST_RUN.get("excluded_reason", ""),
        "seals": int(LAST_RUN.get("seals", 0)),
    }
