"""
Generator for machine_maintenance compliance records (§2.4).

Row schema:
- machine_ref: "MC-0417"
- machine_type: "overlock" | "flatlock" | "cutter" | "boiler" | "generator"
- serviced_on: date string
- hours_since_last: int
- technician_ref: "TCH-12"
- parts_replaced: list of short strings
- next_due_on: date string
- downtime_minutes: int
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np

from ..messiness import MessinessEngine
from ..sites import SiteProfile
from ..timeline import PeriodInfo

MACHINE_TYPES = ("overlock", "flatlock", "cutter", "boiler", "generator")
COMMON_PARTS = [
    "needle bar",
    "looper",
    "oil filter",
    "timing belt",
    "feed dog",
    "knife blade",
    "pressure valve",
    "spark plug",
    "bearing assembly",
    "gasket seal",
]


def generate_maintenance_records(
    site: SiteProfile,
    period_info: PeriodInfo,
    n_rows: int,
    messiness: MessinessEngine,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Generate clean machine maintenance records."""
    rows: list[dict[str, Any]] = []

    for _ in range(n_rows):
        machine_ref = f"MC-{int(rng.integers(1, 1000)):04d}"
        type_raw = MACHINE_TYPES[int(rng.integers(0, len(MACHINE_TYPES)))]
        machine_type = messiness.format_string(type_raw, site, rng)

        day = int(rng.integers(1, 28))
        serviced_date = dt.date(period_info.year, period_info.month, day)

        # Older machinery at Narayanganj has higher service hours
        hours_mean = 450 if site.key == "narayanganj" else 300
        hours_since_last = int(np.clip(rng.normal(hours_mean, 60), 50, 1200))

        technician_ref = f"TCH-{int(rng.integers(1, 25)):02d}"

        # Parts replaced (0 to 3 parts)
        n_parts = int(rng.choice([0, 1, 2, 3], p=[0.40, 0.35, 0.20, 0.05]))
        parts_replaced = [
            str(rng.choice(COMMON_PARTS)) for _ in range(n_parts)
        ]

        # Next due date: typically 30-90 days into future
        due_date = serviced_date + dt.timedelta(days=int(rng.integers(30, 91)))

        downtime_minutes = int(np.clip(rng.normal(45, 20), 10, 360))

        row = {
            "machine_ref": messiness.format_string(machine_ref, site, rng) if messiness.should_apply(site, rng, 0.1) else machine_ref,
            "machine_type": machine_type,
            "serviced_on": messiness.format_date(serviced_date, site, rng),
            "hours_since_last": messiness.format_number(hours_since_last, site, rng),
            "technician_ref": messiness.format_string(technician_ref, site, rng) if messiness.should_apply(site, rng, 0.1) else technician_ref,
            "parts_replaced": parts_replaced,
            "next_due_on": messiness.format_date(due_date, site, rng),
            "downtime_minutes": messiness.format_number(downtime_minutes, site, rng),
        }
        rows.append(row)

    return rows
