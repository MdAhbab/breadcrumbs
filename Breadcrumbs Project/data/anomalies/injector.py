"""
Continuous severity anomaly injector with within-wave drift support.

Applies labelled anomalies directly to row records while tracking:
- Target row index (anomaly_row)
- Graded continuous severity score (0.05 to 1.0)
- Perturbation details for ground truth
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import numpy as np

from ..schemas import make_cas_number, make_iso_certificate_id
from ..sites import (
    HOURLY_RATE_DIVISOR,
    LEGAL_OT_HOURS_MONTHLY,
    OVERTIME_PAY_MULTIPLIER,
    SiteProfile,
)
from ..timeline import PeriodInfo


class AnomalyInjector:
    """Injects graded anomalies into generated compliance document rows."""

    @staticmethod
    def inject(
        record_type: str,
        rows: list[dict[str, Any]],
        kind: str,
        severity: float,
        site: SiteProfile,
        period_info: PeriodInfo,
        rng: np.random.Generator,
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
        """
        Injects an anomaly of the given kind into the document rows.

        Returns:
            (modified_rows, target_row_index, anomaly_metadata)
        """
        n_rows = len(rows)
        target_idx = int(rng.integers(0, n_rows))
        meta: dict[str, Any] = {
            "kind": kind,
            "severity": severity,
            "target_row": target_idx,
            "wave_drift": period_info.wave_progress,
        }

        # Make a copy of rows so originals can be kept for adversary comparisons
        mod_rows = [dict(r) for r in rows]

        if kind == "arithmetic":
            if record_type == "payroll_register":
                # Stated net pay does not equal basic + ot_pay + bonus - deductions
                # Drift shifts severity from obvious (Wave 1 start) to subtle (Wave 1 end)
                effective_sev = max(0.02, severity * (1.0 - 0.5 * period_info.wave_progress))
                # Discrepancy delta: subtle (1-3%) to blatant (20-40%)
                delta_pct = 0.015 + 0.35 * effective_sev
                sign = 1.0 if rng.random() > 0.5 else -1.0

                r = mod_rows[target_idx]
                net = float(r["net_pay_bdt"])
                new_net = round(max(1000.0, net * (1.0 + sign * delta_pct)), 2)
                r["net_pay_bdt"] = new_net
                meta["discrepancy_bdt"] = round(new_net - net, 2)
                meta["delta_pct"] = round(delta_pct, 4)

            elif record_type == "chemical_inventory":
                # Stated closing kg does not equal opening + received - consumed - disposed
                effective_sev = max(0.02, severity * (1.0 - 0.4 * period_info.wave_progress))
                delta_pct = 0.02 + 0.30 * effective_sev
                r = mod_rows[target_idx]
                closing = float(r["closing_kg"])
                new_closing = round(max(0.0, closing * (1.0 + (1.0 if rng.random() > 0.5 else -1.0) * delta_pct)), 2)
                r["closing_kg"] = new_closing
                meta["discrepancy_kg"] = round(new_closing - closing, 2)

        elif kind == "checksum":
            if record_type == "safety_inspection":
                # Mod-97 check digit failure
                mod_rows[target_idx]["certificate_id"] = make_iso_certificate_id(rng, valid=False)
                meta["corrupted_field"] = "certificate_id"

            elif record_type == "chemical_inventory":
                # CAS Registry number check digit failure
                mod_rows[target_idx]["cas_number"] = make_cas_number(rng, valid=False)
                meta["corrupted_field"] = "cas_number"

        elif kind == "overtime":
            if record_type == "payroll_register":
                # Exceeds statutory 48-hour ceiling
                # Severity ranges from subtle (48.5h) to blatant (75.0h)
                extra_hours = 0.5 + float(28.0 * severity)
                excess_ot = round(LEGAL_OT_HOURS_MONTHLY + extra_hours, 2)

                r = mod_rows[target_idx]
                basic = float(r["basic_bdt"])
                bonus = float(r.get("attendance_bonus_bdt", 0.0))
                deductions = float(r["deductions_bdt"])

                ot_rate = round((basic / HOURLY_RATE_DIVISOR) * OVERTIME_PAY_MULTIPLIER, 2)
                ot_pay = round(excess_ot * ot_rate, 2)
                net_pay = round(basic + ot_pay + bonus - deductions, 2)

                r["ot_hours"] = excess_ot
                r["ot_rate_bdt"] = ot_rate
                r["ot_pay_bdt"] = ot_pay
                r["net_pay_bdt"] = net_pay
                meta["excess_ot_hours"] = round(extra_hours, 2)

        elif kind == "backdating":
            if record_type == "safety_inspection":
                # Signed before inspected
                r = mod_rows[target_idx]
                insp_date_str = str(r["inspected_on"]).strip()
                # Parse date handling messiness
                try:
                    insp_date = dt.date.fromisoformat(insp_date_str)
                except ValueError:
                    insp_date = dt.date(period_info.year, period_info.month, 15)

                days_prior = int(1 + 60 * severity)
                backdated_signed = insp_date - dt.timedelta(days=days_prior)
                r["signed_on"] = backdated_signed.isoformat()
                meta["days_backdated"] = days_prior

            elif record_type == "machine_maintenance":
                # Next due date set in the past relative to service date
                r = mod_rows[target_idx]
                try:
                    serv_date = dt.date.fromisoformat(str(r["serviced_on"]).strip())
                except ValueError:
                    serv_date = dt.date(period_info.year, period_info.month, 10)

                past_due = serv_date - dt.timedelta(days=int(5 + 30 * severity))
                r["next_due_on"] = past_due.isoformat()
                meta["days_inverted"] = (serv_date - past_due).days

        elif kind == "outlier":
            if record_type == "payroll_register":
                # Basic wage far above site mean (e.g. 2.5x to 4.5x)
                mult = 2.0 + 2.5 * severity
                r = mod_rows[target_idx]
                basic = round(float(r["basic_bdt"]) * mult, 2)
                ot_rate = round((basic / HOURLY_RATE_DIVISOR) * OVERTIME_PAY_MULTIPLIER, 2)
                ot_pay = round(float(r["ot_hours"]) * ot_rate, 2)
                net_pay = round(basic + ot_pay + float(r["attendance_bonus_bdt"]) - float(r["deductions_bdt"]), 2)

                r["basic_bdt"] = basic
                r["ot_rate_bdt"] = ot_rate
                r["ot_pay_bdt"] = ot_pay
                r["net_pay_bdt"] = net_pay
                meta["wage_multiplier"] = round(mult, 2)

            elif record_type == "chemical_inventory":
                # Consumed amount spike
                r = mod_rows[target_idx]
                r["consumed_kg"] = round(float(r["consumed_kg"]) * (2.5 + 3.0 * severity), 2)
                r["closing_kg"] = round(max(0.0, float(r["opening_kg"]) + float(r["received_kg"]) - float(r["consumed_kg"]) - float(r["disposed_kg"])), 2)
                meta["consumed_multiplier"] = round(2.5 + 3.0 * severity, 2)

            elif record_type == "production_output":
                r = mod_rows[target_idx]
                r["electricity_kwh"] = round(float(r["electricity_kwh"]) * (3.0 + 3.0 * severity), 2)
                meta["electricity_spike"] = True

        elif kind == "duplication":
            if target_idx < n_rows - 1:
                dup_idx = target_idx + 1
            else:
                dup_idx = target_idx - 1

            if record_type == "payroll_register":
                # Same worker reference duplicated with conflicting wages
                target_worker = mod_rows[target_idx]["worker_ref"]
                mod_rows[dup_idx]["worker_ref"] = target_worker
                mod_rows[dup_idx]["net_pay_bdt"] = round(float(mod_rows[dup_idx]["net_pay_bdt"]) * 1.15, 2)
                meta["duplicated_ref"] = target_worker

            elif record_type in ("machine_maintenance", "safety_inspection"):
                ref_key = "machine_ref" if record_type == "machine_maintenance" else "checkpoint_ref"
                target_ref = mod_rows[target_idx][ref_key]
                mod_rows[dup_idx][ref_key] = target_ref
                meta["duplicated_ref"] = target_ref

        elif kind == "roundness":
            # Implausibly round numbers clustered across several rows
            n_cluster = min(n_rows, max(3, int(n_rows * 0.4)))
            start_row = min(target_idx, n_rows - n_cluster)
            for j in range(start_row, start_row + n_cluster):
                if record_type == "payroll_register":
                    mod_rows[j]["basic_bdt"] = float(int(rng.choice([15000, 18000, 20000, 25000])))
                    mod_rows[j]["ot_hours"] = float(int(rng.choice([10, 20, 30, 40])))
                    mod_rows[j]["ot_rate_bdt"] = round(mod_rows[j]["basic_bdt"] / HOURLY_RATE_DIVISOR * OVERTIME_PAY_MULTIPLIER, 2)
                    mod_rows[j]["ot_pay_bdt"] = round(mod_rows[j]["ot_hours"] * mod_rows[j]["ot_rate_bdt"], 2)
                    mod_rows[j]["deductions_bdt"] = float(int(rng.choice([500, 1000, 1500])))
                    bonus = float(mod_rows[j].get("attendance_bonus_bdt", 0.0))
                    mod_rows[j]["net_pay_bdt"] = round(mod_rows[j]["basic_bdt"] + mod_rows[j]["ot_pay_bdt"] + bonus - mod_rows[j]["deductions_bdt"], 2)
                elif record_type == "chemical_inventory":
                    mod_rows[j]["opening_kg"] = float(int(rng.choice([500, 1000, 1500])))
                    mod_rows[j]["received_kg"] = float(int(rng.choice([200, 400, 600])))
                    mod_rows[j]["consumed_kg"] = float(int(rng.choice([100, 200, 300])))
                    mod_rows[j]["disposed_kg"] = 0.0
                    mod_rows[j]["closing_kg"] = mod_rows[j]["opening_kg"] + mod_rows[j]["received_kg"] - mod_rows[j]["consumed_kg"]
            meta["clustered_rows"] = list(range(start_row, start_row + n_cluster))

        elif kind == "benford":
            # Violate first-digit Benford distribution (set leading digits to uniform {7, 8, 9})
            for r in mod_rows:
                if record_type == "payroll_register":
                    digit = int(rng.choice([7, 8, 9]))
                    r["basic_bdt"] = float(f"{digit}{rng.integers(100, 999):03d}.00")
                    r["ot_rate_bdt"] = round(r["basic_bdt"] / HOURLY_RATE_DIVISOR * OVERTIME_PAY_MULTIPLIER, 2)
                    r["ot_pay_bdt"] = round(float(r["ot_hours"]) * r["ot_rate_bdt"], 2)
                    bonus = float(r.get("attendance_bonus_bdt", 0.0))
                    r["net_pay_bdt"] = round(r["basic_bdt"] + r["ot_pay_bdt"] + bonus - float(r["deductions_bdt"]), 2)
                elif record_type == "production_output":
                    digit = int(rng.choice([8, 9]))
                    r["units_produced"] = int(f"{digit}{rng.integers(100, 999):03d}")
            meta["benford_violation"] = True

        elif kind == "cross_inconsistency":
            # Internally 100% consistent within single document, but contradicts paired records!
            # E.g., for payroll, aggregate worker hours / headcount are artificially depressed or inflated
            # while every single row's math, check digits, and ranges are completely valid.
            scale = 0.40 if rng.random() > 0.5 else 2.20
            for r in mod_rows:
                if record_type == "payroll_register":
                    # Scale hours and wages consistently
                    r["ot_hours"] = round(float(r["ot_hours"]) * scale, 2)
                    r["ot_pay_bdt"] = round(r["ot_hours"] * float(r["ot_rate_bdt"]), 2)
                    bonus = float(r.get("attendance_bonus_bdt", 0.0))
                    r["net_pay_bdt"] = round(float(r["basic_bdt"]) + r["ot_pay_bdt"] + bonus - float(r["deductions_bdt"]), 2)
                elif record_type == "production_output":
                    r["units_produced"] = int(float(r["units_produced"]) * scale)
                    r["electricity_kwh"] = round(float(r["electricity_kwh"]) * scale, 2)
            meta["cross_doc_scale"] = scale
            meta["single_doc_valid"] = True

        return mod_rows, target_idx, meta
