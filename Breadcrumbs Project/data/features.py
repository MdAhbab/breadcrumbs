"""
The bridge from the corpus to the detector.

The generator in this package writes documents the way a factory would actually
file them: dates in four formats, numbers stored as strings, enum values in
whatever case the clerk used, trailing whitespace. `messiness.py` puts that
there deliberately, and it is the honest thing to model. But it means a feature
extractor written against clean data does not survive contact with this corpus —
the one in `model/datagen` raises on 99.5% of these documents.

So everything here coerces before it computes. `_num` will take 1234, "1234",
or "1,234.00"; `_date` will take any of the four formats the generator emits.
A field that cannot be coerced becomes absent rather than an exception, because
a detector that crashes on a messy document is useless in the place this system
is meant to run.

WHAT THE FEATURES ARE FOR

Each block targets anomaly kinds from `anomalies/taxonomy.py`:

    arithmetic     stated total does not equal the sum of its parts
    overtime       monthly overtime above the statutory ceiling
    checksum       ISO 45001 mod-97 or CAS check digit fails
    backdating     signed before the event, or due before serviced
    outlier        a value far from the rest of its own document
    duplication    a reference appearing twice with conflicting figures
    roundness      implausibly round values clustered across rows
    benford        first-digit distribution away from Benford's law

The ninth kind, `cross_inconsistency`, is deliberately absent. Those documents
are internally consistent and contradict a *different* document of the same
period, so no single-document feature can see them and none here pretends to.
`test_cross_inconsistency_undetectability.py` in this package is what holds that
claim honest, and any reported per-kind recall should show it near chance.

WHAT IS DELIBERATELY NOT A FEATURE

Messiness itself. Trailing whitespace, mixed date formats and stringified
numbers all correlate with the site (Mirpur is sloppier than Gazipur by
construction), so a model given those as inputs would learn to identify the
factory rather than the fraud. That is the wrong model and it would score well
for the wrong reason. Coerce it away, do not measure it.

Nor is anything identifying: no worker reference, no certificate number, no
site name, no raw date. Every feature is a relative quantity, which is what
makes it defensible to share a model trained on them across a consortium.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from .schemas import validate_cas_number, validate_iso_certificate_id
from .sites import LEGAL_OT_HOURS_MONTHLY

RECORD_TYPES: tuple[str, ...] = (
    "payroll_register",
    "safety_inspection",
    "chemical_inventory",
    "machine_maintenance",
    "production_output",
)

FEATURE_NAMES: tuple[str, ...] = (
    # -- structure, computed for every record type ---------------------------
    "row_count_z",
    "dup_ref_excess",
    "dup_conflict_frac",
    "dup_row_frac",
    "round_frac",
    "benford_dev",
    "high_lead_digit_frac",
    "val_max_abs_z",
    "val_mean_abs_z",
    "val_skew",
    "neg_value_frac",
    # -- arithmetic identities ------------------------------------------------
    "arith_max_residual",
    "arith_mean_residual",
    "arith_frac_mismatched",
    # -- dates ----------------------------------------------------------------
    "date_frac_inverted",
    "date_span_mean_months",
    "date_frac_out_of_period",
    # -- domain rules ---------------------------------------------------------
    "checksum_frac_failed",
    "ot_max_ratio",
    "ot_frac_over_legal",
    # -- which kind of document this is ---------------------------------------
    "is_payroll",
    "is_safety",
    "is_chemical",
    "is_maintenance",
    "is_production",
)
N_FEATURES = len(FEATURE_NAMES)
_IDX = {name: i for i, name in enumerate(FEATURE_NAMES)}

# The reference row count the corpus generates around, used to centre
# `row_count_z`. A document with far fewer or more rows than its peers is worth
# noticing on its own.
_ROWS_REFERENCE = 24.0
_ROWS_SCALE = 16.0

# Which numeric field carries the signal for each record type. Used for the
# outlier block: one row far from its own document's median is the tell.
_PRINCIPAL_FIELD: Mapping[str, str] = {
    "payroll_register": "basic_bdt",
    "chemical_inventory": "consumed_kg",
    "production_output": "electricity_kwh",
    "machine_maintenance": "downtime_minutes",
    "safety_inspection": "",  # no continuous quantity to speak of
}

# The reference whose repetition means duplication, per record type.
#
# `production_output` is deliberately absent. Its `line_ref` repeats by design —
# one row per production line per day — so counting repeats there measures the
# calendar, not a fault. Including it made the average clean document look more
# duplicated than the average planted one, and the detector correctly learned to
# ignore the feature. A reference belongs here only where a second appearance
# within one document is itself the anomaly.
_REF_FIELD: Mapping[str, str] = {
    "payroll_register": "worker_ref",
    "safety_inspection": "checkpoint_ref",
    "chemical_inventory": "substance_ref",
    "machine_maintenance": "machine_ref",
}

_BENFORD = np.log10(1.0 + 1.0 / np.arange(1, 10))


# ---------------------------------------------------------------------------
# Coercion. Everything messy is normalised here and nowhere else.
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

# Fields that hold a date, and reference-like fields that hold digits without
# holding a quantity. Both must stay out of any numeric statistic.
_NON_QUANTITY_SUFFIXES = (
    "_ref", "_code", "_id", "_number", "_zone", "_mode",
    "_on", "_date", "_due", "_at",
)


def _is_quantity(key: str, value: Any) -> bool:
    """
    Whether a field is a number to do arithmetic on.

    A date is not. `paid_on` reaches this module as "2025-03-28" from a tidy
    site and "28/03/2025" from a sloppy one, and a bare number-scraping regex
    reads those as 2025 and 28 — so a date silently entered the leading-digit
    and roundness statistics with a value that depended on which factory filed
    it. That is precisely the site-identity leak this module promises not to
    have, and it was invisible until the messiness test compared the same
    document filed two ways.
    """
    if key.endswith(_NON_QUANTITY_SUFFIXES):
        return False
    return _date(value) is None


def _num(value: Any) -> float | None:
    """A float from a number, a numeric string, or a formatted string."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        match = _NUM_RE.search(value.strip().replace(",", ""))
        if match:
            try:
                out = float(match.group())
            except ValueError:
                return None
            return out if math.isfinite(out) else None
    return None


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y")


def _date(value: Any) -> dt.date | None:
    """A date from any of the four formats `messiness.format_date` emits."""
    if isinstance(value, dt.date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _text(value: Any) -> str:
    """A comparable string: stripped and case-folded."""
    return str(value).strip().lower() if value is not None else ""


def _column(rows: Sequence[Mapping[str, Any]], key: str) -> np.ndarray:
    """Every coercible value of one field, as a float array."""
    out = [v for v in (_num(r.get(key)) for r in rows) if v is not None]
    return np.asarray(out, dtype=np.float64)


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

def _rows_disagree(group: Sequence[Mapping[str, Any]]) -> bool:
    """Whether rows sharing a reference disagree on any numeric field."""
    keys = {k for row in group for k in row}
    for key in keys:
        values = [_num(row.get(key)) for row in group]
        present = [v for v in values if v is not None]
        if len(present) > 1 and max(present) - min(present) > 1e-6:
            return True
    return False


def _numeric_pool(rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    """Every coercible numeric value in the document, for Benford and roundness."""
    pool: list[float] = []
    for row in rows:
        for key, value in row.items():
            if not _is_quantity(key, value):
                continue
            got = _num(value)
            if got is not None:
                pool.append(got)
    return np.asarray(pool, dtype=np.float64)


def _benford_deviation(values: np.ndarray) -> float:
    """Total absolute deviation of the leading-digit distribution from Benford."""
    magnitudes = np.abs(values)
    magnitudes = magnitudes[magnitudes >= 1.0]
    if magnitudes.size < 8:
        return 0.0
    leading = np.array([int(str(int(v))[0]) for v in magnitudes])
    observed = np.array([(leading == d).mean() for d in range(1, 10)])
    return float(np.abs(observed - _BENFORD).sum())


def _high_leading_digit(rows: Sequence[Mapping[str, Any]]) -> float:
    """
    The most extreme concentration of leading digits in 7, 8 or 9, by column.

    Benford's law puts about 15.5% of naturally occurring leading digits in
    {7,8,9}. The generator's Benford anomaly rewrites one column so that every
    value starts with one of them, which is a much sharper thing to look for
    than a deviation score.

    Three things this had to get right, all of them found by measurement rather
    than assumed:

      per column, not pooled. One rewritten column among a dozen honest ones in
      different units vanishes into a pooled histogram, which is why the first
      version of this scored zero recall on the anomaly it was written for.

      a magnitude floor, not a dynamic-range test. Small-range integer fields
      like `grade` and `days_worked` have no business obeying Benford and would
      otherwise dominate the maximum. The obvious guard — requiring the column
      to cross a power of ten — is exactly wrong here, because the attack works
      by *narrowing* the column to 7000-9999, so that guard skipped the one
      column carrying the signal.

      at least six distinct values, so a column repeating one figure is not
      mistaken for a fabricated distribution.

    On the corpus's cross-wave benchmark this separates completely: the median
    Benford-anomalous document scores 1.0 and the median clean document 0.0,
    with the 99th percentile of clean documents at 0.24.
    """
    columns: dict[str, list[float]] = {}
    for row in rows:
        for key, value in row.items():
            if not _is_quantity(key, value):
                continue
            got = _num(value)
            if got is not None and abs(got) >= 1000.0:
                columns.setdefault(key, []).append(abs(got))
    worst = 0.0
    for values in columns.values():
        if len(values) < 8 or len(set(values)) < 6:
            continue
        leading = np.array([int(str(int(v))[0]) for v in values])
        worst = max(worst, float(np.mean(leading >= 7)))
    return worst


def _round_fraction(values: np.ndarray) -> float:
    """
    How much of the document sits on implausibly round numbers.

    The generator's `roundness` anomaly plants values like 15000 and 500 across
    a cluster of rows. Ordinary generated values carry two decimal places, so
    exact multiples of 100 are rare enough for this to separate.
    """
    if values.size == 0:
        return 0.0
    interesting = values[np.abs(values) >= 100.0]
    if interesting.size == 0:
        return 0.0
    return float(np.mean(np.abs(interesting % 100.0) < 1e-9))


def _robust_z(values: np.ndarray) -> np.ndarray:
    """
    Distance from the document's own median, scaled by its own spread.

    Median and MAD rather than mean and standard deviation, because a single
    planted outlier drags a mean toward itself and hides in its own inflated
    variance. That is exactly the case this feature exists to catch.
    """
    if values.size < 3:
        return np.zeros_like(values)
    median = np.median(values)
    mad = np.median(np.abs(values - median))
    scale = mad * 1.4826 if mad > 1e-9 else max(1e-6, float(np.std(values)))
    if scale <= 1e-9:
        return np.zeros_like(values)
    return (values - median) / scale


def _arithmetic_residuals(record_type: str, rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    """
    Relative error in each row's stated total.

    Two identities in this corpus, both from the record builders:
        payroll   net_pay = basic + ot_pay + attendance_bonus - deductions
        chemical  closing = opening + received - consumed - disposed
    Relative rather than absolute, so a large wage and a small one contribute
    on the same scale.
    """
    residuals: list[float] = []
    for row in rows:
        if record_type == "payroll_register":
            parts = [_num(row.get(k)) for k in
                     ("basic_bdt", "ot_pay_bdt", "attendance_bonus_bdt", "deductions_bdt")]
            stated = _num(row.get("net_pay_bdt"))
            if stated is None or any(p is None for p in parts):
                continue
            basic, ot_pay, bonus, deductions = parts  # type: ignore[misc]
            expected = basic + ot_pay + bonus - deductions
        elif record_type == "chemical_inventory":
            parts = [_num(row.get(k)) for k in
                     ("opening_kg", "received_kg", "consumed_kg", "disposed_kg")]
            stated = _num(row.get("closing_kg"))
            if stated is None or any(p is None for p in parts):
                continue
            opening, received, consumed, disposed = parts  # type: ignore[misc]
            expected = opening + received - consumed - disposed
            # The generator clamps a stated closing balance at zero, so a stock
            # that would have gone negative is not an arithmetic fault.
            if expected < 0.0 and abs(stated) < 1e-9:
                continue
        else:
            return np.zeros(0, dtype=np.float64)
        residuals.append(abs(stated - expected) / max(1.0, abs(expected)))
    return np.asarray(residuals, dtype=np.float64)


def _date_pairs(record_type: str, rows: Sequence[Mapping[str, Any]]) -> list[tuple[dt.date, dt.date]]:
    """
    (earlier-by-rule, later-by-rule) pairs, so inversion means back-dating.

    safety      a certificate is signed on or after the inspection
    maintenance the next service falls due after the one just performed
    """
    keys = {
        "safety_inspection": ("inspected_on", "signed_on"),
        "machine_maintenance": ("serviced_on", "next_due_on"),
    }.get(record_type)
    if keys is None:
        return []
    out: list[tuple[dt.date, dt.date]] = []
    for row in rows:
        first, second = _date(row.get(keys[0])), _date(row.get(keys[1]))
        if first is not None and second is not None:
            out.append((first, second))
    return out


def _checksum_failures(record_type: str, rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
    """Check-digit validity, where the record type carries a checked identifier."""
    if record_type == "safety_inspection":
        key, validate = "certificate_id", validate_iso_certificate_id
    elif record_type == "chemical_inventory":
        key, validate = "cas_number", validate_cas_number
    else:
        return np.zeros(0, dtype=np.float64)
    flags = [0.0 if validate(str(row[key]).strip()) else 1.0 for row in rows if key in row]
    return np.asarray(flags, dtype=np.float64)


# ---------------------------------------------------------------------------
# The extractor
# ---------------------------------------------------------------------------

def extract_features(document: Mapping[str, Any]) -> np.ndarray:
    """
    One document to one fixed-length vector.

    Takes a plain mapping — a line of the corpus JSONL, parsed — so this works
    on a streamed shard without building an object per document.
    """
    record_type = _text(document.get("record_type")).replace(" ", "_")
    rows = [r for r in document.get("rows") or [] if isinstance(r, Mapping)]
    f = np.zeros(N_FEATURES, dtype=np.float64)
    if not rows:
        return f
    n = len(rows)

    # -- structure ----------------------------------------------------------
    f[_IDX["row_count_z"]] = (n - _ROWS_REFERENCE) / _ROWS_SCALE

    ref_key = _REF_FIELD.get(record_type, "")
    if ref_key:
        # A raw count of excess references, not a fraction of the document.
        # One duplicate worker in a register of twenty-two is a fraction of
        # 0.045 — small enough to vanish once the column is standardised, which
        # is why an earlier version of this extractor recovered barely a tenth
        # of the planted duplications. The count is 1 either way, whatever the
        # document's length, and that is the quantity that actually means
        # "somebody appears twice".
        groups: dict[str, list[Mapping[str, Any]]] = {}
        for row in rows:
            if row.get(ref_key) is not None:
                groups.setdefault(_text(row.get(ref_key)), []).append(row)
        if groups:
            f[_IDX["dup_ref_excess"]] = float(sum(len(g) - 1 for g in groups.values()))
            # Sharper still: a reference repeated with *conflicting* figures.
            # Two rows for one worker with the same numbers is a filing slip;
            # two rows with different pay is the anomaly the generator plants.
            repeated = [g for g in groups.values() if len(g) > 1]
            if repeated:
                conflicting = sum(1 for g in repeated if _rows_disagree(g))
                f[_IDX["dup_conflict_frac"]] = conflicting / len(repeated)

    fingerprints = [tuple(sorted((k, _text(v)) for k, v in r.items())) for r in rows]
    f[_IDX["dup_row_frac"]] = 1.0 - len(set(fingerprints)) / n

    pool = _numeric_pool(rows)
    f[_IDX["round_frac"]] = _round_fraction(pool)
    f[_IDX["benford_dev"]] = _benford_deviation(pool)
    f[_IDX["high_lead_digit_frac"]] = _high_leading_digit(rows)

    principal = _PRINCIPAL_FIELD.get(record_type, "")
    if principal:
        values = _column(rows, principal)
        z = _robust_z(values)
        if z.size:
            f[_IDX["val_max_abs_z"]] = float(np.abs(z).max())
            f[_IDX["val_mean_abs_z"]] = float(np.abs(z).mean())
            spread = z.std()
            if spread > 1e-9:
                f[_IDX["val_skew"]] = float(((z - z.mean()) ** 3).mean() / spread**3)
        if values.size:
            f[_IDX["neg_value_frac"]] = float(np.mean(values < 0.0))

    # -- arithmetic ---------------------------------------------------------
    residuals = _arithmetic_residuals(record_type, rows)
    if residuals.size:
        f[_IDX["arith_max_residual"]] = float(residuals.max())
        f[_IDX["arith_mean_residual"]] = float(residuals.mean())
        # A tolerance, not zero: the builders round to two decimals, so an
        # honest row carries a residual of order 1e-7 rather than exactly 0.
        f[_IDX["arith_frac_mismatched"]] = float(np.mean(residuals > 1e-4))

    # -- dates --------------------------------------------------------------
    pairs = _date_pairs(record_type, rows)
    if pairs:
        spans = np.array([(later - earlier).days for earlier, later in pairs], dtype=np.float64)
        f[_IDX["date_frac_inverted"]] = float(np.mean(spans < 0))
        f[_IDX["date_span_mean_months"]] = float(spans.mean()) / 30.0

    period = _text(document.get("period"))
    if len(period) == 7 and period[4] == "-":
        stamps = [
            _date(r.get(k))
            for r in rows
            for k in ("paid_on", "inspected_on", "serviced_on", "output_date")
            if k in r
        ]
        stamps = [s for s in stamps if s is not None]
        if stamps:
            f[_IDX["date_frac_out_of_period"]] = float(
                np.mean([s.strftime("%Y-%m") != period for s in stamps])
            )

    # -- domain rules -------------------------------------------------------
    failures = _checksum_failures(record_type, rows)
    if failures.size:
        f[_IDX["checksum_frac_failed"]] = float(failures.mean())

    if record_type == "payroll_register":
        hours = _column(rows, "ot_hours")
        if hours.size:
            f[_IDX["ot_max_ratio"]] = float(hours.max()) / LEGAL_OT_HOURS_MONTHLY
            f[_IDX["ot_frac_over_legal"]] = float(np.mean(hours > LEGAL_OT_HOURS_MONTHLY))

    # -- which kind of document ---------------------------------------------
    onehot = {
        "payroll_register": "is_payroll",
        "safety_inspection": "is_safety",
        "chemical_inventory": "is_chemical",
        "machine_maintenance": "is_maintenance",
        "production_output": "is_production",
    }.get(record_type)
    if onehot:
        f[_IDX[onehot]] = 1.0

    return f


def build_matrix(
    documents: Iterable[Mapping[str, Any]],
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """
    Feature matrix, binary labels, and anomaly kind per document.

    The kind is carried alongside rather than folded into the label so that
    per-kind recall can be reported — which is the only way to show honestly
    that `cross_inconsistency` is not detected from a single document.
    """
    xs, ys, kinds = [], [], []
    for document in documents:
        xs.append(extract_features(document))
        ys.append(int(document.get("label") or 0))
        kinds.append(str(document.get("anomaly_kind") or "clean"))
    if not xs:
        return np.zeros((0, N_FEATURES)), np.zeros(0, dtype=int), []
    return np.vstack(xs), np.asarray(ys, dtype=int), kinds


__all__ = [
    "FEATURE_NAMES",
    "N_FEATURES",
    "RECORD_TYPES",
    "build_matrix",
    "extract_features",
]
