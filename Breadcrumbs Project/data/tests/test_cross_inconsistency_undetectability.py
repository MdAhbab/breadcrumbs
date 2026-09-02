"""
Acceptance Test 8: cross_inconsistency is undetectable from a single document alone.
"""

from __future__ import annotations

import datetime as dt

from data.generator import DocumentGenerator
from data.schemas import validate_iso_certificate_id, validate_row_schema


def parse_date(d_str: str) -> dt.date:
    d_str = str(d_str).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(d_str, fmt).date()
        except ValueError:
            pass
    return dt.date.fromisoformat(d_str)


def test_cross_inconsistency_documents_are_internally_consistent():
    """
    Assert that documents with cross_inconsistency anomalies pass all single-document
    schema, arithmetic, and range validations in isolation.
    """
    gen = DocumentGenerator(seed=42)
    # Generate 50 cross_inconsistency documents
    docs = gen.generate_of_kind("cross_inconsistency", 50)
    assert len(docs) == 50

    for doc in docs:
        assert doc.label == 1
        assert doc.anomaly_kind == "cross_inconsistency"

        # 1. Row schema validation
        for row in doc.rows:
            ok, msg = validate_row_schema(doc.record_type, row)
            assert ok, f"Schema error on cross_inconsistency doc: {msg}"

        # 2. Internal arithmetic check (must pass 100% within the single document)
        if doc.record_type == "payroll_register":
            for row in doc.rows:
                basic = float(row["basic_bdt"])
                ot_hours = float(row["ot_hours"])
                ot_rate = float(row["ot_rate_bdt"])
                ot_pay = float(row["ot_pay_bdt"])
                deductions = float(row["deductions_bdt"])
                bonus = float(row.get("attendance_bonus_bdt", 0.0))
                net_pay = float(row["net_pay_bdt"])

                # Check ot_pay = ot_hours * ot_rate
                expected_ot_pay = round(ot_hours * ot_rate, 2)
                assert abs(ot_pay - expected_ot_pay) < 0.05, (
                    f"Single-doc arithmetic violated in ot_pay: {ot_pay} != {expected_ot_pay}"
                )

                # Check net_pay = basic + ot_pay + bonus - deductions
                expected_net = round(basic + ot_pay + bonus - deductions, 2)
                assert abs(net_pay - expected_net) < 0.05, (
                    f"Single-doc arithmetic violated in net_pay: {net_pay} != {expected_net}"
                )

        elif doc.record_type == "safety_inspection":
            # Checksums and dates must be clean
            for row in doc.rows:
                assert validate_iso_certificate_id(row["certificate_id"])
                # Signed on or after inspected
                assert parse_date(row["signed_on"]) >= parse_date(row["inspected_on"])
