"""
Tests for the corpus-to-detector bridge.

Each of these attacks a claim the extractor makes rather than checking that it
runs. The claims are: it survives every document the generator can emit, it is
not fooled by the messiness the generator plants on purpose, it does not smuggle
identity into the feature vector, and it does not pretend to see the one anomaly
kind that is invisible from a single document.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from data.features import (
    FEATURE_NAMES,
    N_FEATURES,
    build_matrix,
    extract_features,
)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
BENCHMARK = CORPUS / "benchmarks" / "cross_wave.jsonl.gz"

pytestmark = pytest.mark.skipif(
    not BENCHMARK.exists(), reason="no corpus generated; run python -m data.cli"
)


def _documents(path: Path) -> list[dict]:
    with gzip.open(path, "rt") as handle:
        return [json.loads(line) for line in handle if line.strip()]


@pytest.fixture(scope="module")
def benchmark() -> list[dict]:
    return _documents(BENCHMARK)


@pytest.fixture(scope="module")
def matrix(benchmark):
    return build_matrix(benchmark)


def test_every_document_extracts(benchmark):
    """
    No document in the corpus may raise.

    This is the test that would have caught the original problem: the extractor
    in `model/datagen` was written against a clean generator and raised on 99.5%
    of these documents, because they carry stringified numbers and four date
    formats by design.
    """
    for document in benchmark:
        vector = extract_features(document)
        assert vector.shape == (N_FEATURES,)
        assert np.isfinite(vector).all(), document["doc_id"]


def test_feature_names_match_width():
    assert len(FEATURE_NAMES) == N_FEATURES
    assert len(set(FEATURE_NAMES)) == N_FEATURES


def test_extraction_is_deterministic(benchmark):
    for document in benchmark[:200]:
        assert np.array_equal(extract_features(document), extract_features(document))


def test_empty_and_malformed_documents_do_not_raise():
    assert np.isfinite(extract_features({})).all()
    assert np.isfinite(extract_features({"record_type": "payroll_register", "rows": []})).all()
    assert np.isfinite(extract_features({"record_type": "nonsense", "rows": [{"a": "b"}]})).all()


def test_messiness_does_not_change_the_features():
    """
    The same document filed sloppily must extract to the same vector.

    Numbers as strings, a different date format, casing and trailing whitespace
    are all things `messiness.py` applies as a function of which site filed the
    document. If any of them moved a feature, the detector could learn to
    recognise the factory instead of the fraud.
    """
    clean = {
        "record_type": "payroll_register",
        "period": "2025-03",
        "rows": [
            {
                "worker_ref": f"W-{i:04d}", "grade": 3, "days_worked": 26,
                "basic_bdt": 12500.0 + i, "ot_hours": 10.0, "ot_rate_bdt": 90.0,
                "ot_pay_bdt": 900.0, "attendance_bonus_bdt": 500.0,
                "deductions_bdt": 300.0, "net_pay_bdt": 12500.0 + i + 900.0 + 500.0 - 300.0,
                "payment_mode": "bank", "paid_on": "2025-03-28",
            }
            for i in range(12)
        ],
    }
    messy = {
        "record_type": "  Payroll_Register  ",
        "period": "2025-03",
        "rows": [
            {
                "worker_ref": f"w-{i:04d}  ", "grade": "3", "days_worked": "26",
                "basic_bdt": f"{12500.0 + i:.2f}", "ot_hours": "10.00",
                "ot_rate_bdt": "90.00", "ot_pay_bdt": "900.00",
                "attendance_bonus_bdt": "500.00", "deductions_bdt": "300.00",
                "net_pay_bdt": f"{12500.0 + i + 1100.0:.2f}",
                "payment_mode": "BANK", "paid_on": "28/03/2025",
            }
            for i in range(12)
        ],
    }
    assert np.allclose(extract_features(clean), extract_features(messy), atol=1e-9)


def test_all_four_date_formats_are_understood():
    """Every format `messiness.format_date` can emit must parse to the same day."""
    base = {
        "record_type": "safety_inspection",
        "period": "2025-04",
        "rows": [],
    }
    for stamp in ("2025-04-10", "10/04/2025", "2025/04/10", "10-04-2025"):
        document = dict(base, rows=[
            {
                "checkpoint_ref": f"CP-{i}", "category": "fire", "result": "pass",
                "certificate_id": "ISO45001-1234556", "inspected_on": stamp,
                "signed_on": stamp, "inspector_ref": "INS-1",
                "remediation_due": stamp, "notes": "",
            }
            for i in range(10)
        ])
        vector = extract_features(document)
        # Signed on the day of inspection: nothing inverted, no span.
        assert vector[FEATURE_NAMES.index("date_frac_inverted")] == 0.0
        assert vector[FEATURE_NAMES.index("date_span_mean_months")] == 0.0
        assert vector[FEATURE_NAMES.index("date_frac_out_of_period")] == 0.0


@pytest.mark.parametrize(
    "kind,feature",
    [
        ("arithmetic", "arith_max_residual"),
        ("checksum", "checksum_frac_failed"),
        ("backdating", "date_frac_inverted"),
        ("overtime", "ot_frac_over_legal"),
        ("roundness", "round_frac"),
        ("duplication", "dup_conflict_frac"),
        ("benford", "high_lead_digit_frac"),
    ],
)
def test_each_kind_moves_the_feature_written_for_it(matrix, benchmark, kind, feature):
    """
    Every anomaly kind with a dedicated feature must actually move it.

    Stated as a comparison of medians rather than of means so a handful of
    extreme documents cannot carry the claim on their own.
    """
    x, _, kinds = matrix
    kinds = np.asarray(kinds)
    column = FEATURE_NAMES.index(feature)
    planted = x[kinds == kind, column]
    clean = x[kinds == "clean", column]
    assert planted.size, f"no {kind} documents in the benchmark"
    assert np.median(planted) > np.median(clean), (
        f"{feature} does not separate {kind}: "
        f"median {np.median(planted):.4f} vs clean {np.median(clean):.4f}"
    )


def test_cross_inconsistency_is_not_claimed_to_be_visible(matrix):
    """
    The one kind the extractor must NOT appear to detect.

    A cross-inconsistent document is internally consistent and contradicts a
    different document of the same period. If any single-document feature
    separated it, either the generator is not producing what it says it is or a
    feature is keying on something incidental — and either way a per-kind recall
    reported from this extractor would be dishonest.
    """
    x, _, kinds = matrix
    kinds = np.asarray(kinds)
    subject = x[kinds == "cross_inconsistency"]
    clean = x[kinds == "clean"]
    assert subject.size, "no cross_inconsistency documents in the benchmark"

    for column, name in enumerate(FEATURE_NAMES):
        if name.startswith("is_"):
            continue  # record type is not evidence of anomaly
        reference = clean[:, column]
        spread = np.median(np.abs(reference - np.median(reference))) * 1.4826
        if spread < 1e-9:
            spread = reference.std()
        if spread < 1e-9:
            continue
        shift = abs(np.median(subject[:, column]) - np.median(reference)) / spread
        assert shift < 1.0, f"{name} appears to separate cross_inconsistency by {shift:.2f}"


def test_clean_payroll_arithmetic_is_consistent(matrix):
    """A clean register's stated totals must add up, within rounding."""
    x, _, kinds = matrix
    kinds = np.asarray(kinds)
    residual = x[kinds == "clean", FEATURE_NAMES.index("arith_mean_residual")]
    assert float(np.max(residual)) < 1e-3


def test_build_matrix_shapes(matrix, benchmark):
    x, y, kinds = matrix
    assert x.shape == (len(benchmark), N_FEATURES)
    assert y.shape == (len(benchmark),)
    assert len(kinds) == len(benchmark)
    assert set(np.unique(y).tolist()) <= {0, 1}
    # A document is labelled anomalous exactly when it carries a kind.
    assert all((k != "clean") == bool(label) for k, label in zip(kinds, y, strict=True))


def test_build_matrix_handles_no_documents():
    x, y, kinds = build_matrix([])
    assert x.shape == (0, N_FEATURES) and y.shape == (0,) and kinds == []
