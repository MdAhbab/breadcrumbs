"""
What a viewer may read of a document body, column by column.

The API never served a document body at all, on the principle that the only way
data leaves is one row at a time through a proof. That principle is right about
*disclosure* and wrong about *comprehension*: a buyer looking at a record page
saw a row count and a hash and had no idea what the document was, so "we are
protecting the other 1,846 rows" was a claim they had to take on faith.

So a preview exists, and it is built to make the boundary legible rather than to
work around it:

  * the owner sees its own document, because it is its own document;
  * everyone else sees every column *name* and a handful of rows, with each cell
    either readable or visibly withheld, and the reason attached;
  * a cell that is withheld is never sent. It is dropped here, in the response
    body, not hidden in the browser — a preview that shipped the value and
    styled it out would be a leak with a stylesheet in front of it.

Columns identifying a person are withheld from everyone but the owner, and a
grant does not open them. A grant is a licence to check one figure, not to learn
whose figure it is; the proof path treats a row index the same way.
"""

from __future__ import annotations

from typing import Any

# People. Never shown to a non-owner, grant or no grant.
IDENTITY_FIELDS = {
    "worker_ref",
    "worker_name",
    "employee_id",
    "employee_ref",
    "technician_ref",
    "inspector_ref",
    "operator_ref",
    "supervisor_ref",
}

# Substrings that mark a column as personal wherever it turns up. A corpus grows
# new columns; the classification should not have to be edited every time one
# arrives with an obvious name.
IDENTITY_HINTS = (
    "national_id", "nid", "passport", "phone", "mobile", "email",
    "address", "account_no", "bank_account", "_name",
)

# Structural context: what kind of thing each row is and when it happened.
# Readable by anyone entitled to open the record, because without it the other
# columns cannot be understood at all — and none of it is about a person.
OPEN_FIELDS = {
    "category", "machine_ref", "machine_type", "checkpoint_ref", "substance_ref",
    "storage_zone", "cas_number", "certificate_id", "result", "payment_mode",
    "msds_on_file", "zdhc_listed", "parts_replaced", "notes",
    "paid_on", "serviced_on", "inspected_on", "signed_on", "next_due_on",
    "remediation_due", "period", "site",
}

LABELS = {
    "worker_ref": "Worker",
    "basic_bdt": "Basic pay (BDT)",
    "ot_hours": "Overtime hours",
    "ot_rate_bdt": "Overtime rate (BDT)",
    "ot_pay_bdt": "Overtime pay (BDT)",
    "net_pay_bdt": "Net pay (BDT)",
    "deductions_bdt": "Deductions (BDT)",
    "attendance_bonus_bdt": "Attendance bonus (BDT)",
    "days_worked": "Days worked",
    "paid_on": "Paid on",
    "cas_number": "CAS number",
    "msds_on_file": "Safety sheet on file",
    "zdhc_listed": "ZDHC listed",
    "closing_kg": "Closing stock (kg)",
    "opening_kg": "Opening stock (kg)",
    "consumed_kg": "Consumed (kg)",
    "received_kg": "Received (kg)",
    "disposed_kg": "Disposed (kg)",
}


def label_for(field: str) -> str:
    """A column heading a person can read, without inventing a vocabulary."""
    if field in LABELS:
        return LABELS[field]
    text = field.replace("_", " ")
    for suffix, unit in (("bdt", "(BDT)"), ("kg", "(kg)"), ("ref", "")):
        if text.endswith(f" {suffix}"):
            text = f"{text[: -len(suffix) - 1]} {unit}".strip()
    return text[:1].upper() + text[1:]


def classify(field: str) -> str:
    """`identity`, `open`, or `sensitive` — in that order of precedence."""
    lowered = field.lower()
    if lowered in IDENTITY_FIELDS or any(h in lowered for h in IDENTITY_HINTS):
        return "identity"
    if lowered in OPEN_FIELDS:
        return "open"
    return "sensitive"


def columns_of(rows: list[dict[str, Any]]) -> list[str]:
    """
    Every column that appears, in first-seen order.

    Not `rows[0].keys()`: a row carrying an optional column would otherwise
    decide the shape of the whole table, and the preview's job is to show the
    document's shape honestly.
    """
    seen: list[str] = []
    for row in rows:
        for key in row:
            if key not in seen:
                seen.append(key)
    return seen


def redact(
    rows: list[dict[str, Any]],
    *,
    is_owner: bool,
    granted_fields: set[str],
    limit: int = 8,
    is_auditor: bool = False,
) -> dict[str, Any]:
    """
    A preview of `rows`, with everything this viewer may not read left out.

    Returns the columns with their classification and whether each is readable,
    plus the first `limit` rows carrying only the readable cells.

    `is_auditor` opens the figures without a grant, and deliberately does not
    open the people. An auditor's job is to check whether the numbers are right,
    which needs every number and none of the names; see `scoping.py` for why the
    role gets that access at all.
    """
    fields = columns_of(rows)
    shown = rows[: max(limit, 0)]

    columns = []
    for field in fields:
        kind = classify(field)
        if is_owner:
            visible, why = True, "your own document"
        elif kind == "identity":
            visible, why = False, "identifies a person"
        elif field in granted_fields:
            visible, why = True, "covered by your access"
        elif kind == "open":
            visible, why = True, "describes the record, not a person"
        elif is_auditor:
            visible, why = True, "open to you as an auditor"
        else:
            visible, why = False, "no access to this column"
        columns.append(
            {
                "name": field,
                "label": label_for(field),
                "kind": kind,
                "visible": visible,
                "reason": why,
            }
        )

    readable = {c["name"] for c in columns if c["visible"]}
    return {
        "columns": columns,
        # Only the readable cells cross the wire.
        "rows": [{k: v for k, v in row.items() if k in readable} for row in shown],
        "total_rows": len(rows),
        "shown_rows": len(shown),
        "readable_columns": len(readable),
        "total_columns": len(fields),
    }
