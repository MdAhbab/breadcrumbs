"""
Generator for production_output records (§2.5).

One row per production line per operational day.
This type exists for cross-checking against payroll_register (§7.6).

Row schema:
- line_ref: "L-03"
- output_date: date string
- units_produced: int
- workers_present: int
- machine_hours: float
- electricity_kwh: float
- buyer_code: "BYR-04"
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np

from ..messiness import MessinessEngine
from ..sites import SiteProfile
from ..timeline import PeriodInfo


def generate_production_records(
    site: SiteProfile,
    period_info: PeriodInfo,
    n_rows: int,
    messiness: MessinessEngine,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Generate clean production output rows with physical consistency."""
    rows: list[dict[str, Any]] = []

    # Production volume boost during peak season
    prod_boost = site.peak_production_boost if period_info.is_peak_season else 1.0

    # Operational lines for this factory
    n_lines = max(4, int(site.worker_count / 150))

    for _ in range(n_rows):
        line_idx = int(rng.integers(1, n_lines + 1))
        line_ref = f"L-{line_idx:02d}"

        day = int(rng.integers(1, 27))  # 26 operational days
        output_date = dt.date(period_info.year, period_info.month, day)

        # Physical relationship: workers present on line -> machine hours -> units produced -> electricity
        workers_present = int(rng.integers(25, 60))
        machine_hours = round(float(np.clip(rng.normal(8.0 * (1.1 if period_info.is_peak_season else 1.0), 0.8), 6.0, 14.0)), 2)

        # Units produced ~ 15-25 units per worker per hour
        hourly_rate_per_worker = float(rng.uniform(1.8, 2.6))
        units = int(workers_present * machine_hours * hourly_rate_per_worker * prod_boost)

        # Electricity ~ 1.8 to 3.2 kWh per machine hour per line
        electricity_kwh = round(float(machine_hours * rng.uniform(28.0, 48.0)), 2)

        buyer_code = str(rng.choice(site.buyer_codes))

        row = {
            "line_ref": messiness.format_string(line_ref, site, rng) if messiness.should_apply(site, rng, 0.1) else line_ref,
            "output_date": messiness.format_date(output_date, site, rng),
            "units_produced": messiness.format_number(units, site, rng),
            "workers_present": messiness.format_number(workers_present, site, rng),
            "machine_hours": messiness.format_number(machine_hours, site, rng),
            "electricity_kwh": messiness.format_number(electricity_kwh, site, rng),
            "buyer_code": messiness.format_string(buyer_code, site, rng) if messiness.should_apply(site, rng, 0.1) else buyer_code,
        }
        rows.append(row)

    return rows
