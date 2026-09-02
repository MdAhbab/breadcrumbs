"""
Generator for chemical_inventory compliance records (§2.3).

Row schema:
- substance_ref: "CHM-0231"
- cas_number: plausible CAS format with valid check digit
- opening_kg: float
- received_kg: float
- consumed_kg: float
- disposed_kg: float
- closing_kg: float (normally opening + received - consumed - disposed)
- zdhc_listed: bool
- msds_on_file: bool
- storage_zone: "A".."F"
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..messiness import MessinessEngine
from ..schemas import make_cas_number
from ..sites import SiteProfile
from ..timeline import PeriodInfo

STORAGE_ZONES = ("A", "B", "C", "D", "E", "F")


def generate_chemical_records(
    site: SiteProfile,
    period_info: PeriodInfo,
    n_rows: int,
    messiness: MessinessEngine,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Generate clean chemical inventory rows."""
    rows: list[dict[str, Any]] = []

    for i in range(n_rows):
        substance_ref = f"CHM-{i + 1:04d}"
        cas_number = make_cas_number(rng, valid=True)

        # Scale chemical consumption by site operations (Chattogram has highest volume)
        vol_scale = 1.8 if site.key == "chattogram" else 1.0
        opening_kg = round(float(rng.uniform(100.0, 1500.0) * vol_scale), 2)
        received_kg = round(float(rng.uniform(50.0, 800.0) * vol_scale), 2)
        consumed_kg = round(float(rng.uniform(40.0, opening_kg + received_kg - 20.0)), 2)
        disposed_kg = round(float(rng.uniform(0.0, 30.0)), 2)

        closing_kg = round(opening_kg + received_kg - consumed_kg - disposed_kg, 2)

        zdhc_listed = bool(rng.random() > 0.15)
        msds_on_file = bool(rng.random() > 0.05)

        zone_idx = int(rng.integers(0, len(STORAGE_ZONES)))
        storage_zone = messiness.format_string(STORAGE_ZONES[zone_idx], site, rng)

        row = {
            "substance_ref": messiness.format_string(substance_ref, site, rng) if messiness.should_apply(site, rng, 0.1) else substance_ref,
            "cas_number": cas_number,
            "opening_kg": messiness.format_number(opening_kg, site, rng),
            "received_kg": messiness.format_number(received_kg, site, rng),
            "consumed_kg": messiness.format_number(consumed_kg, site, rng),
            "disposed_kg": messiness.format_number(disposed_kg, site, rng),
            "closing_kg": messiness.format_number(closing_kg, site, rng),
            "zdhc_listed": zdhc_listed,
            "msds_on_file": msds_on_file,
            "storage_zone": storage_zone,
        }
        rows.append(row)

    return rows
