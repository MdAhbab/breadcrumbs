"""
Generator for safety_inspection compliance records (§2.2).

Row schema:
- checkpoint_ref: "CP-014"
- category: "fire" | "electrical" | "structural" | "chemical" | "egress"
- certificate_id: "ISO45001-NNNNNCC" where CC = NNNNN mod 97
- inspected_on: date string
- signed_on: date string (normally 0-10 days after inspected_on)
- inspector_ref: "INS-07"
- result: "pass" | "remediate" | "fail"
- remediation_due: date string or null
- notes: free text, often empty
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np

from ..messiness import MessinessEngine
from ..schemas import make_iso_certificate_id
from ..sites import SiteProfile
from ..timeline import PeriodInfo

CATEGORIES = ("fire", "electrical", "structural", "chemical", "egress")
RESULTS = ("pass", "remediate", "fail")


def generate_safety_records(
    site: SiteProfile,
    period_info: PeriodInfo,
    n_rows: int,
    messiness: MessinessEngine,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Generate clean safety inspection rows."""
    rows: list[dict[str, Any]] = []

    for i in range(n_rows):
        checkpoint_ref = f"CP-{i + 1:03d}"
        category_raw = CATEGORIES[int(rng.integers(0, len(CATEGORIES)))]
        category = messiness.format_string(category_raw, site, rng)

        cert_id = make_iso_certificate_id(rng, valid=True)

        day = int(rng.integers(1, 28))
        inspected_date = dt.date(period_info.year, period_info.month, day)

        # In clean rows, signing strictly happens 0-10 days AFTER inspection
        signing_delay = int(rng.integers(0, 11))
        signed_date = inspected_date + dt.timedelta(days=signing_delay)

        inspector_ref = f"INS-{int(rng.integers(1, 16)):02d}"

        # Result distribution (pass 85%, remediate 12%, fail 3%)
        res_choice = int(rng.choice([0, 1, 2], p=[0.85, 0.12, 0.03]))
        result_raw = RESULTS[res_choice]
        result = messiness.format_string(result_raw, site, rng)

        if result_raw in ("remediate", "fail"):
            rem_due_date = inspected_date + dt.timedelta(days=int(rng.integers(14, 45)))
            remediation_due = messiness.format_date(rem_due_date, site, rng)
        else:
            remediation_due = None

        notes = messiness.sample_note(site, rng)

        row = {
            "checkpoint_ref": messiness.format_string(checkpoint_ref, site, rng) if messiness.should_apply(site, rng, 0.1) else checkpoint_ref,
            "category": category,
            "certificate_id": cert_id,
            "inspected_on": messiness.format_date(inspected_date, site, rng),
            "signed_on": messiness.format_date(signed_date, site, rng),
            "inspector_ref": messiness.format_string(inspector_ref, site, rng) if messiness.should_apply(site, rng, 0.1) else inspector_ref,
            "result": result,
            "remediation_due": remediation_due,
            "notes": notes,
        }
        rows.append(row)

    return rows
