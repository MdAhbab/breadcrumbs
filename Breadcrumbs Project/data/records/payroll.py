"""
Generator for payroll_register compliance records (§2.1).

Row schema:
- worker_ref: "W-04182" (stable pseudonymous reference, never a name)
- grade: 1..7
- days_worked: 0..26
- basic_bdt: float
- ot_hours: float
- ot_rate_bdt: float (normally basic / 208 * 2)
- ot_pay_bdt: float (normally ot_hours * ot_rate_bdt)
- attendance_bonus_bdt: float (often 0)
- deductions_bdt: float (advances, PF, absence)
- net_pay_bdt: float (normally basic + ot_pay + bonus - deductions)
- payment_mode: "bank" | "mfs" | "cash"
- paid_on: date string
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np

from ..messiness import MessinessEngine
from ..sites import (
    BASE_MINIMUM_WAGE_BDT,
    HOURLY_RATE_DIVISOR,
    LEGAL_OT_HOURS_MONTHLY,
    OVERTIME_PAY_MULTIPLIER,
    SiteProfile,
)
from ..timeline import PeriodInfo

PAYMENT_MODES = ("bank", "mfs", "cash")


def generate_payroll_records(
    site: SiteProfile,
    period_info: PeriodInfo,
    n_rows: int,
    messiness: MessinessEngine,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    """Generate clean payroll register rows conforming strictly to domain rules."""
    rows: list[dict[str, Any]] = []

    # Seasonal overtime multiplier
    ot_scale = site.peak_overtime_boost if period_info.is_peak_season else 1.0

    # Calculate payment date (within first 7 days of the following month)
    pay_year = period_info.year if period_info.month < 12 else period_info.year + 1
    pay_month = period_info.month + 1 if period_info.month < 12 else 1
    base_pay_date = dt.date(pay_year, pay_month, int(rng.integers(1, 8)))

    # Grade distribution: RMG grades 1..7 (most workers are Grade 4-6, Grade 7 is entry)
    for _ in range(n_rows):
        # Stable worker reference
        worker_id = int(rng.integers(1, site.worker_count + 1))
        worker_ref = f"W-{worker_id:05d}"

        # Grade (1 = highest skilled, 7 = entry level apprentice)
        grade = int(rng.choice([1, 2, 3, 4, 5, 6, 7], p=[0.05, 0.10, 0.15, 0.25, 0.25, 0.15, 0.05]))

        # Base wage tied to grade and site baseline
        # Grade 7 = minimum wage; Grade 1 = ~1.65x minimum wage
        grade_multiplier = 1.0 + (7 - grade) * 0.10
        worker_mean = site.mean_basic_wage * grade_multiplier
        basic_bdt = float(rng.normal(worker_mean, worker_mean * 0.04))
        basic_bdt = max(BASE_MINIMUM_WAGE_BDT, round(basic_bdt, 2))

        # Days worked (out of standard 26 days)
        if rng.random() > 0.08:
            days_worked = int(rng.integers(24, 27))
        else:
            days_worked = int(rng.integers(18, 24))

        # Overtime hours (normally between 0 and 48 statutory limit)
        mean_ot = 24.0 * ot_scale
        ot_hours = float(np.clip(rng.normal(mean_ot, 8.0), 0.0, LEGAL_OT_HOURS_MONTHLY - 0.5))
        ot_hours = round(ot_hours, 2)

        # Overtime rate = basic / 208 * 2
        ot_rate_bdt = round((basic_bdt / HOURLY_RATE_DIVISOR) * OVERTIME_PAY_MULTIPLIER, 2)
        ot_pay_bdt = round(ot_hours * ot_rate_bdt, 2)

        # Attendance bonus (full attendance = bonus)
        attendance_bonus_bdt = 500.0 if days_worked >= 26 and rng.random() > 0.3 else 0.0

        # Deductions (PF 5% + occasional advance or absence deduction)
        pf_deduction = basic_bdt * 0.05
        absence_deduction = (basic_bdt / 26.0) * (26 - days_worked)
        other_deduction = float(rng.integers(0, 500)) if rng.random() < 0.10 else 0.0
        deductions_bdt = round(pf_deduction + absence_deduction + other_deduction, 2)

        # Net pay calculation
        net_pay_bdt = round(basic_bdt + ot_pay_bdt + attendance_bonus_bdt - deductions_bdt, 2)

        # Payment mode
        mode_idx = int(rng.choice([0, 1, 2], p=[0.45, 0.45, 0.10]))
        payment_mode = messiness.format_string(PAYMENT_MODES[mode_idx], site, rng)

        paid_on = messiness.format_date(base_pay_date, site, rng)

        row = {
            "worker_ref": messiness.format_string(worker_ref, site, rng) if messiness.should_apply(site, rng, 0.1) else worker_ref,
            "grade": messiness.format_number(grade, site, rng),
            "days_worked": messiness.format_number(days_worked, site, rng),
            "basic_bdt": messiness.format_number(basic_bdt, site, rng),
            "ot_hours": messiness.format_number(ot_hours, site, rng),
            "ot_rate_bdt": messiness.format_number(ot_rate_bdt, site, rng),
            "ot_pay_bdt": messiness.format_number(ot_pay_bdt, site, rng),
            "attendance_bonus_bdt": messiness.format_number(attendance_bonus_bdt, site, rng),
            "deductions_bdt": messiness.format_number(deductions_bdt, site, rng),
            "net_pay_bdt": messiness.format_number(net_pay_bdt, site, rng),
            "payment_mode": payment_mode,
            "paid_on": paid_on,
        }
        rows.append(row)

    return rows
