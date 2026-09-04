"""Governance, membership, SLA, incidents, notifications and the regulator view."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from model.consortium import DOCUMENT_CHANNEL, MODEL_CHANNEL

from .. import ledger_service as ledger
from ..auth import CurrentUser, require_capability
from ..db import Incident, Notification, Proposal, as_dict, get_session

router = APIRouter(tags=["governance"])


def _now() -> str:
    """A real timestamp, in the format the chaincode compares against."""
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/governance/proposals")
def proposals(user: CurrentUser, db: Session = Depends(get_session)) -> list[dict]:
    require_capability(user, "read_governance")
    out = []
    for p in db.query(Proposal).order_by(Proposal.opened_at.desc()).all():
        d = as_dict(p)
        d["endorsement_count"] = len(p.endorsers)
        d["threshold_reached"] = len(p.endorsers) >= p.required
        d["effect"] = _effect(p)
        out.append(d)
    return out


def _execute(p: Proposal, user: CurrentUser) -> dict | None:
    """
    Carry out a motion that has reached its threshold.

    This is the half that was missing. Endorsing used to flip a string in a SQL
    row to "approved" and stop, so the governance screen could carry a motion to
    admit a factory, show it as passed, and leave that factory absent from the
    register, absent from the network map and absent from the ledger. The one
    screen in the product about collective decisions was the one screen where a
    decision changed nothing.

    A motion executes exactly once. `executed_tx` is the guard: a second
    endorsement, or a restart mid-flight, must not admit the same organisation
    twice, and the chaincode would refuse the duplicate anyway.

    A policy change has no subject and nothing to execute. That is honest rather
    than incomplete: this prototype does not model charter text on-chain, and
    inventing a transaction for it would be the same fiction being removed here.
    """
    if p.executed_tx or not p.subject:
        return None

    subject = dict(p.subject)
    if p.kind == "new_member":
        return ledger.invoke(
            MODEL_CHANNEL, "membership", "admit_member",
            {**subject, "proposal_id": p.id, "endorsers": list(p.endorsers),
             "timestamp": _now()},
            user.role, endorsers=ledger.gate_endorsers(), timestamp=_now(),
        )
    if p.kind == "suspension":
        return ledger.invoke(
            MODEL_CHANNEL, "membership", "set_status",
            {**subject, "proposal_id": p.id, "timestamp": _now()},
            user.role, endorsers=ledger.gate_endorsers(), timestamp=_now(),
        )
    return None


@router.post("/governance/proposals/{proposal_id}/endorse")
def endorse(proposal_id: str, user: CurrentUser, db: Session = Depends(get_session)) -> dict:
    require_capability(user, "write_governance")
    p = db.get(Proposal, proposal_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no proposal {proposal_id}")
    if user.msp_id in p.endorsers:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{user.msp_id} has already endorsed this proposal"
        )
    # Endorsements count organisations, never individual signatures — the same
    # rule the endorsement policy engine applies on-chain.
    p.endorsers = [*p.endorsers, user.msp_id]

    executed = None
    if len(p.endorsers) >= p.required:
        p.status = "approved"
        try:
            executed = _execute(p, user)
        except ledger.LedgerError as exc:
            # The tally is a fact and it stands; what failed is carrying the
            # motion out. Saying so is better than a green motion and a register
            # that quietly disagrees with it.
            db.commit()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {"code": exc.code, "message": f"the motion carried but could not be "
                                              f"executed: {exc.message}"},
            ) from exc
        if executed:
            p.executed_tx = executed["tx_id"]

    db.commit()
    return {
        "proposal_id": proposal_id,
        "endorsements": len(p.endorsers),
        "required": p.required,
        "status": p.status,
        "executed_tx": p.executed_tx,
        "effect": _effect(p),
    }


def _effect(p: Proposal) -> str | None:
    """What carrying this motion did, in one sentence, or why it did nothing."""
    if not p.subject:
        return (
            "A policy change is recorded here and is not enforced on-chain by this "
            "prototype." if p.status == "approved" else None
        )
    if p.status != "approved":
        return None
    if not p.executed_tx:
        return "Carried, but not yet written to the ledger."
    if p.kind == "new_member":
        return f"{p.subject.get('name', p.subject['msp_id'])} is now on the register."
    if p.kind == "suspension":
        return f"{p.subject['msp_id']} is now {p.subject.get('status', 'suspended')}."
    return None


@router.get("/governance/members")
def members(user: CurrentUser) -> list[dict]:
    """
    The register, read off the ledger rather than off a constant.

    It used to be a list literal, which meant an admitted member could never
    appear here no matter what the consortium decided.
    """
    require_capability(user, "read_governance")
    rows = ledger.query(MODEL_CHANNEL, "membership", "list_members", {}, user.role)
    return [
        {
            "org": r["name"],
            "msp_id": r["msp_id"],
            "role": r["kind"],
            "country": r["country"],
            "status": r["status"],
            "founding": r["founding"],
            "admitted_at": r["admitted_at"],
            "proposal_id": r["proposal_id"],
        }
        for r in rows
    ]


@router.get("/ops/sla")
def sla(user: CurrentUser, db: Session = Depends(get_session)) -> dict:
    """
    Operations, split into what is counted and what is not measured.

    Verifications are counted from the receipts on the chain *at request time*.
    They used to be read from a table written once during the seed, so an auditor
    could verify fifty records and the operations page would still report the
    four it had been born with. A figure that stops moving when the thing it
    counts moves is not a measurement.

    Uptime and response time are not measured at all: this prototype runs no
    monitoring, and a 99.95% figure with a flat green line under it would be a
    decorative number in a product whose whole argument is that decorative
    numbers are the problem. They are reported as unmeasured, with the reason.
    """
    require_capability(user, "read_sla")

    receipts = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "list_receipts", {}, user.role
    ) or []
    per_day: dict[str, int] = {}
    for receipt in receipts:
        day = str(receipt.get("verified_at", ""))[:10]
        if day:
            per_day[day] = per_day.get(day, 0) + 1

    points = [
        {"day": day, "verifications": count, "uptime_pct": None, "avg_response_ms": None}
        for day, count in sorted(per_day.items())
    ]

    return {
        "points": points,
        "kpis": {
            "total_verifications": len(receipts),
            "days_observed": len(points),
            "monthly_uptime_pct": None,
            "uptime_target_pct": 99.5,
            "avg_response_ms": None,
            "response_target_ms": 500,
            "rpo": "15 min",
            "rto": "4 hr",
        },
        "unmeasured": {
            "fields": ["monthly_uptime_pct", "avg_response_ms"],
            "reason": (
                "This prototype runs no uptime or latency monitoring. The targets "
                "are the consortium's service-level commitments; the observed "
                "figures do not exist and are not invented here."
            ),
        },
        "incidents": [as_dict(i) for i in db.query(Incident).all()],
    }


@router.get("/ops/incidents/{incident_id}")
def incident(incident_id: str, user: CurrentUser, db: Session = Depends(get_session)) -> dict:
    require_capability(user, "read_sla")
    found = db.get(Incident, incident_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no incident {incident_id}")
    return as_dict(found)


@router.get("/notifications")
def notifications(user: CurrentUser, db: Session = Depends(get_session)) -> list[dict]:
    require_capability(user, "read_directory")
    rows = (
        db.query(Notification)
        .filter(Notification.audience_msp == user.msp_id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [as_dict(n) for n in rows]


@router.get("/regulator/overview")
def regulator_overview(user: CurrentUser, db: Session = Depends(get_session)) -> dict:
    """
    Aggregates and governance events only.

    No factory record reaches this endpoint, for any caller. The regulator screen
    shows its restrictions rather than hiding them, and this is where that is
    actually true rather than merely displayed.
    """
    require_capability(user, "read_governance")
    proposals_all = db.query(Proposal).all()
    register = ledger.query(MODEL_CHANNEL, "membership", "list_members", {}, user.role)
    return {
        "read_only_notice": (
            "Read-only observer access. Aggregate governance statistics and events "
            "only. Factory-level records and personal data require a separate "
            "lawful-basis access grant."
        ),
        "kpis": {
            # Counted off the register, so admitting or suspending a member
            # moves these figures. They used to be a length of a constant, which
            # meant the observatory reported the same numbers for ever.
            "active_factories": sum(
                1 for m in register if m["kind"] == "factory" and m["status"] == "active"
            ),
            "total_organisations": sum(1 for m in register if m["status"] == "active"),
            "open_proposals": sum(1 for p in proposals_all if p.status == "pending"),
            "schema_versions_in_use": 4,
        },
        "governance_events": [
            {
                "kind": p.kind,
                "title": p.title,
                "status": p.status,
                "opened_at": p.opened_at,
                "org": "BGMEA Consortium",
            }
            for p in proposals_all
        ],
        "chain": ledger.chain_summary(),
    }
