"""
Who may see which record, and which reporting period.

The rule lives here rather than being written out again in each handler,
because the previous version of this API leaked precisely by having it in more
than one place.

  * a factory sees its own;
  * a buyer sees only what it holds a live grant against;
  * an auditor sees every document on the channel;
  * the regulator sees none.

The auditor is the deliberate asymmetry, and it is worth stating plainly rather
than leaving it to be discovered. An auditor is a contracted certification body
whose entire job is to inspect the documents it is auditing, and making it beg
for a grant per column reproduced in software the thing that makes real audits
useless: the audited party choosing what the auditor is allowed to look at.

What this does NOT do is give the auditor personal data. Columns identifying a
person stay withheld from everyone except the owner — see `redaction.py` — so
an auditor can check every wage in a register without learning whose wages they
are. Nor does it change what a *buyer* sees, which is still one column per
grant, and it does not make an auditor's reading of a figure into proof: only a
receipt on the ledger does that.
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
    if user.role == "auditor":
        records = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "list_records", {}, user.role
        )
        return {r["bucket"] for r in records}
    if user.role == "buyer":
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
    """The records this caller may see. The one definition; see the module note."""
    records = ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_records", {}, user.role)
    if user.role == "consortium":
        return records
    if user.role == "factory":
        return [r for r in records if r["owner_msp"] == user.msp_id]
    if user.role == "auditor":
        return records
    if user.role == "buyer":
        grants = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "list_grants",
            {"requester_msp": user.msp_id}, user.role,
        )
        granted = {g["record_id"] for g in grants if g["status"] == "active"}
        return [r for r in records if r["record_id"] in granted]
    return []
