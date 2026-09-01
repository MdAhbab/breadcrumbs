"""
Who may see which reporting period.

Seals are consortium-visible facts about a factory's bookkeeping, which is not
the same as being public. The rule is the same one that governs records — a
factory sees its own, a buyer or auditor sees only what it holds a live grant
against, the regulator sees none — and it lives here rather than being written
out again in each handler, because the previous version of this API leaked
precisely by having the rule in more than one place.
"""

from __future__ import annotations

from typing import Any

from model.consortium import DOCUMENT_CHANNEL

from . import ledger_service as ledger
from .auth import Principal


def visible_buckets(user: Principal) -> set[str] | None:
    """
    The buckets this caller may read. `None` means "every bucket".

    Returning None rather than a set of everything keeps the consortium case
    from silently becoming a stale snapshot of whatever existed at call time.
    """
    if user.role == "consortium":
        return None
    if user.role == "factory":
        records = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "list_records", {}, user.role
        )
        return {r["bucket"] for r in records if r["owner_msp"] == user.msp_id}
    if user.role in ("buyer", "auditor"):
        grants = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "list_grants",
            {"requester_msp": user.msp_id}, user.role,
        )
        granted = {g["record_id"] for g in grants if g["status"] == "active"}
        records = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "list_records", {}, user.role
        )
        return {r["bucket"] for r in records if r["record_id"] in granted}
    # The regulator has no seal capability at all; this is belt and braces.
    return set()


def may_see_bucket(user: Principal, bucket: str) -> bool:
    allowed = visible_buckets(user)
    return allowed is None or bucket in allowed


def scoped_records(user: Principal) -> list[dict[str, Any]]:
    """The records this caller may see, by the same rule as `/api/records`."""
    records = ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_records", {}, user.role)
    if user.role == "consortium":
        return records
    if user.role == "factory":
        return [r for r in records if r["owner_msp"] == user.msp_id]
    if user.role in ("buyer", "auditor"):
        grants = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "list_grants",
            {"requester_msp": user.msp_id}, user.role,
        )
        granted = {g["record_id"] for g in grants if g["status"] == "active"}
        return [r for r in records if r["record_id"] in granted]
    return []
