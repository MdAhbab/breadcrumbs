"""Governance, membership, SLA, incidents, notifications and the regulator view."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from model.consortium import ORGS

from .. import ledger_service as ledger
from ..auth import CurrentUser, deny_read_only
from ..db import Incident, Notification, Proposal, SlaPoint, as_dict, get_session

router = APIRouter(tags=["governance"])


@router.get("/governance/proposals")
def proposals(user: CurrentUser, db: Session = Depends(get_session)) -> list[dict]:
    out = []
    for p in db.query(Proposal).order_by(Proposal.opened_at.desc()).all():
        d = as_dict(p)
        d["endorsement_count"] = len(p.endorsers)
        d["threshold_reached"] = len(p.endorsers) >= p.required
        out.append(d)
    return out


@router.post("/governance/proposals/{proposal_id}/endorse")
def endorse(proposal_id: str, user: CurrentUser, db: Session = Depends(get_session)) -> dict:
    deny_read_only(user)
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
    if len(p.endorsers) >= p.required:
        p.status = "approved"
    db.commit()
    return {
        "proposal_id": proposal_id,
        "endorsements": len(p.endorsers),
        "required": p.required,
        "status": p.status,
    }


@router.get("/governance/members")
def members(user: CurrentUser) -> list[dict]:
    return [
        {"org": name, "msp_id": msp_id, "role": kind, "country": country, "status": "active"}
        for msp_id, name, kind, country in ORGS
    ]


@router.get("/ops/sla")
def sla(user: CurrentUser, db: Session = Depends(get_session)) -> dict:
    points = db.query(SlaPoint).order_by(SlaPoint.day).all()
    if not points:
        return {"points": [], "kpis": {}}
    uptimes = [float(p.uptime_pct) for p in points]
    return {
        "points": [as_dict(p) for p in points],
        "kpis": {
            "monthly_uptime_pct": round(sum(uptimes) / len(uptimes), 3),
            "uptime_target_pct": 99.5,
            "total_verifications": sum(p.verifications for p in points),
            "avg_response_ms": round(sum(p.avg_response_ms for p in points) / len(points)),
            "response_target_ms": 500,
            "rpo": "15 min",
            "rto": "4 hr",
        },
        "incidents": [as_dict(i) for i in db.query(Incident).all()],
    }


@router.get("/ops/incidents/{incident_id}")
def incident(incident_id: str, user: CurrentUser, db: Session = Depends(get_session)) -> dict:
    found = db.get(Incident, incident_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no incident {incident_id}")
    return as_dict(found)


@router.get("/notifications")
def notifications(user: CurrentUser, db: Session = Depends(get_session)) -> list[dict]:
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
    proposals_all = db.query(Proposal).all()
    return {
        "read_only_notice": (
            "Read-only observer access. Aggregate governance statistics and events "
            "only. Factory-level records and personal data require a separate "
            "lawful-basis access grant."
        ),
        "kpis": {
            "active_factories": sum(1 for o in ORGS if o[2] == "factory"),
            "total_organisations": len(ORGS),
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
