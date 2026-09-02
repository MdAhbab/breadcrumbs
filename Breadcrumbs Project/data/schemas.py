"""
Row schemas, validation routines, and cryptographic / algorithmic check-digit generators.

Contains implementations for:
- ISO 45001 Mod-97 certificate check digit calculation and validation.
- Chemical Abstract Service (CAS) Registry Number check digit calculation and validation.
- Row-level schema validation across all 5 record types.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Check-digit algorithms
# ---------------------------------------------------------------------------

def calculate_iso_mod97_check_digit(body: int) -> int:
    """Mod-97 check digit for certificate serial numbers."""
    return body % 97


def make_iso_certificate_id(rng: np.random.Generator, valid: bool = True) -> str:
    """Generate ISO45001-NNNNNCC certificate ID with valid or invalid Mod-97 check digit."""
    body = int(rng.integers(10_000, 99_999))
    check = calculate_iso_mod97_check_digit(body)
    if not valid:
        # Guarantee corrupted check digit
        offset = int(rng.integers(1, 96))
        check = (check + offset) % 97
    return f"ISO45001-{body:05d}{check:02d}"


def validate_iso_certificate_id(cert_id: str) -> bool:
    """
    Validate ISO45001-NNNNNCC string format and Mod-97 check digit.
    Only the serial after the hyphen is checked.
    """
    if not isinstance(cert_id, str):
        return False
    parts = cert_id.strip().split("-")
    if len(parts) < 2:
        return False
    serial = parts[-1]
    if len(serial) != 7 or not serial.isdigit():
        return False
    body = int(serial[:5])
    check = int(serial[5:])
    return (body % 97) == check


def calculate_cas_check_digit(base_digits: str) -> int:
    """
    Calculate CAS Registry Number check digit.
    Weights are 1, 2, 3... from right to left on the base digits.
    Check digit is (sum % 10).
    """
    digits = [int(d) for d in base_digits if d.isdigit()]
    total = sum((i + 1) * d for i, d in enumerate(reversed(digits)))
    return total % 10


def make_cas_number(rng: np.random.Generator, valid: bool = True) -> str:
    """
    Generate plausible CAS Registry Number in format XXXXXXX-YY-Z.
    2-7 digits in first segment, 2 digits in second segment, 1 check digit.
    """
    prefix_len = int(rng.integers(2, 6))
    prefix = "".join(str(rng.integers(0, 10)) for _ in range(prefix_len))
    # Ensure no leading zero in CAS prefix
    if prefix.startswith("0"):
        prefix = str(rng.integers(1, 10)) + prefix[1:]
    mid = f"{rng.integers(10, 99):02d}"
    base = prefix + mid
    check = calculate_cas_check_digit(base)
    if not valid:
        # Guarantee corrupted check digit
        check = (check + int(rng.integers(1, 9))) % 10
    return f"{prefix}-{mid}-{check}"


def validate_cas_number(cas_no: str) -> bool:
    """Validate CAS Registry Number format and checksum."""
    if not isinstance(cas_no, str):
        return False
    match = re.fullmatch(r"(\d{2,7})-(\d{2})-(\d)", cas_no.strip())
    if not match:
        return False
    prefix, mid, check_str = match.groups()
    base = prefix + mid
    expected_check = calculate_cas_check_digit(base)
    return int(check_str) == expected_check


# ---------------------------------------------------------------------------
# Schema Definitions and Validators
# ---------------------------------------------------------------------------

SCHEMA_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "payroll_register": (
        "worker_ref",
        "grade",
        "days_worked",
        "basic_bdt",
        "ot_hours",
        "ot_rate_bdt",
        "ot_pay_bdt",
        "attendance_bonus_bdt",
        "deductions_bdt",
        "net_pay_bdt",
        "payment_mode",
        "paid_on",
    ),
    "safety_inspection": (
        "checkpoint_ref",
        "category",
        "certificate_id",
        "inspected_on",
        "signed_on",
        "inspector_ref",
        "result",
        "remediation_due",
        "notes",
    ),
    "chemical_inventory": (
        "substance_ref",
        "cas_number",
        "opening_kg",
        "received_kg",
        "consumed_kg",
        "disposed_kg",
        "closing_kg",
        "zdhc_listed",
        "msds_on_file",
        "storage_zone",
    ),
    "machine_maintenance": (
        "machine_ref",
        "machine_type",
        "serviced_on",
        "hours_since_last",
        "technician_ref",
        "parts_replaced",
        "next_due_on",
        "downtime_minutes",
    ),
    "production_output": (
        "line_ref",
        "output_date",
        "units_produced",
        "workers_present",
        "machine_hours",
        "electricity_kwh",
        "buyer_code",
    ),
}


def validate_row_schema(record_type: str, row: dict[str, Any]) -> tuple[bool, str]:
    """
    Check that a raw row contains all required fields for its record type and has valid types.
    Allows for realistic messiness (e.g. numeric values stored as strings, or None in optional fields).
    """
    if record_type not in SCHEMA_REQUIRED_FIELDS:
        return False, f"Unknown record type: {record_type}"

    required = SCHEMA_REQUIRED_FIELDS[record_type]
    for field_name in required:
        if field_name not in row:
            return False, f"Missing required field '{field_name}' in {record_type} row"

    # Type-specific checks (case-insensitive prefixes to support realistic casing variations)
    if record_type == "payroll_register":
        if not str(row["worker_ref"]).strip().upper().startswith("W-"):
            return False, f"Invalid worker_ref format: {row['worker_ref']}"
        # Validate grade 1..7 (can be int or numeric string)
        try:
            grade = int(row["grade"])
            if not (1 <= grade <= 7):
                return False, f"Grade {grade} out of range 1..7"
        except (ValueError, TypeError):
            return False, f"Invalid grade type: {row['grade']}"

    elif record_type == "safety_inspection":
        if not str(row["checkpoint_ref"]).strip().upper().startswith("CP-"):
            return False, f"Invalid checkpoint_ref: {row['checkpoint_ref']}"
        if not str(row["inspector_ref"]).strip().upper().startswith("INS-"):
            return False, f"Invalid inspector_ref: {row['inspector_ref']}"

    elif record_type == "chemical_inventory":
        if not str(row["substance_ref"]).strip().upper().startswith("CHM-"):
            return False, f"Invalid substance_ref: {row['substance_ref']}"

    elif record_type == "machine_maintenance":
        if not str(row["machine_ref"]).strip().upper().startswith("MC-"):
            return False, f"Invalid machine_ref: {row['machine_ref']}"
        if not isinstance(row["parts_replaced"], (list, tuple)):
            return False, f"parts_replaced must be list: {type(row['parts_replaced'])}"

    elif record_type == "production_output":
        if not str(row["line_ref"]).strip().upper().startswith("L-"):
            return False, f"Invalid line_ref: {row['line_ref']}"
        if not str(row["buyer_code"]).strip().upper().startswith("BYR-"):
            return False, f"Invalid buyer_code: {row['buyer_code']}"

    return True, "OK"
