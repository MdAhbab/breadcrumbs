"""
Invented compliance documents with planted, labelled anomalies.

Nothing here is real. No factory supplied data, no worker exists, and the
anomaly rate is chosen rather than observed. That is a limitation the report
states plainly and it should be stated the same way in any demo: this generator
makes it possible to *measure* a detector honestly, not to claim a measurement
about the industry.

What makes it useful is that the anomalies are of kinds a real compliance
reviewer looks for, and each one is labelled, so detection can be scored rather
than eyeballed:

  arithmetic       stated totals do not equal the sum of their components
  checksum         a certificate identifier fails its issuing body's check digit
  overtime         hours exceed the legal ceiling for the period
  backdating       a record is signed before the event it describes
  outlier          a value sits far from what this site normally reports

Features are extracted locally at the factory and only features ever leave the
building. The extractor is deliberately in this file next to the generator so it
is obvious which fields the model sees: no names, no national IDs, no addresses.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

SITES = ["Gazipur", "Ashulia", "Narayanganj", "Savar", "Chattogram", "Mirpur"]
RECORD_TYPES = [
    "payroll_register",
    "safety_inspection",
    "chemical_inventory",
    "machine_maintenance",
    "compliance_certificate",
]
ANOMALY_KINDS = ["arithmetic", "checksum", "overtime", "backdating", "outlier"]

# Bangladesh minimum wage for the RMG sector, and the statutory overtime ceiling.
# Used to shape plausible numbers; not a legal reference.
BASE_WAGE_BDT = 12_500
LEGAL_OT_HOURS = 12 * 4  # 12 hours a week over a four-week period


@dataclass
class Document:
    """One generated document. `label` is the ground truth a detector is scored on."""

    doc_id: str
    record_type: str
    site: str
    period: str
    rows: list[dict[str, Any]]
    label: int  # 0 clean, 1 anomalous
    anomaly_kind: str | None
    anomaly_row: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _checksum_ok(identifier: str) -> bool:
    """
    A mod-97 check digit, in the spirit of an issuing body's format.

    Only the serial after the hyphen is checked. Taking every digit in the
    string would fold the scheme name's own digits ("ISO45001") into the
    arithmetic, and then no identifier would ever validate — which makes the
    feature pure noise instead of a signal.
    """
    serial = "".join(c for c in identifier.split("-")[-1] if c.isdigit())
    if len(serial) < 3:
        return False
    body, check = int(serial[:-2]), int(serial[-2:])
    return body % 97 == check


def _make_identifier(rng: np.random.Generator, valid: bool) -> str:
    body = int(rng.integers(10_000, 99_999))
    check = body % 97
    if not valid:
        check = (check + int(rng.integers(1, 96))) % 97
    return f"ISO45001-{body:05d}{check:02d}"


class DocumentGenerator:
    """Generates a labelled corpus. Seeded, so a demo is reproducible."""

    def __init__(self, seed: int = 7, anomaly_rate: float = 0.04):
        self.rng = np.random.default_rng(seed)
        self.anomaly_rate = anomaly_rate
        # Each site has its own normal range, so "far from what this site
        # normally reports" means something.
        self.site_mean = {
            s: BASE_WAGE_BDT * (1.0 + 0.12 * i / len(SITES)) for i, s in enumerate(SITES)
        }

    # -- record bodies ----------------------------------------------------
    def _payroll(self, site: str, n_rows: int, anomaly: str | None) -> tuple[list[dict], int | None]:
        mean = self.site_mean[site]
        rows = []
        for i in range(n_rows):
            basic = float(self.rng.normal(mean, mean * 0.08))
            ot_hours = float(abs(self.rng.normal(28, 9)))
            ot_rate = basic / 208 * 2
            ot_pay = ot_hours * ot_rate
            deductions = basic * 0.085
            rows.append(
                {
                    "worker_ref": f"W-{i:05d}",  # a reference, never a name
                    "basic_bdt": round(basic, 2),
                    "ot_hours": round(ot_hours, 2),
                    "ot_pay_bdt": round(ot_pay, 2),
                    "deductions_bdt": round(deductions, 2),
                    "net_pay_bdt": round(basic + ot_pay - deductions, 2),
                }
            )

        if anomaly is None:
            return rows, None

        idx = int(self.rng.integers(0, n_rows))
        if anomaly == "arithmetic":
            # The net does not equal basic + overtime - deductions.
            rows[idx]["net_pay_bdt"] = round(rows[idx]["net_pay_bdt"] * 1.19, 2)
        elif anomaly == "overtime":
            rows[idx]["ot_hours"] = round(float(LEGAL_OT_HOURS + self.rng.uniform(6, 30)), 2)
            r = rows[idx]
            r["ot_pay_bdt"] = round(r["ot_hours"] * r["basic_bdt"] / 208 * 2, 2)
            r["net_pay_bdt"] = round(r["basic_bdt"] + r["ot_pay_bdt"] - r["deductions_bdt"], 2)
        elif anomaly == "outlier":
            rows[idx]["basic_bdt"] = round(rows[idx]["basic_bdt"] * 2.6, 2)
        else:
            # Anomaly kinds that do not apply to a payroll body are expressed in
            # the document header instead; see generate().
            return rows, idx
        return rows, idx

    def _inspection(self, n_rows: int, anomaly: str | None) -> tuple[list[dict], int | None]:
        """
        A safety inspection sheet.

        A clean row is always signed on or after the day it was inspected. Giving
        both dates independently at random would make half of every clean
        document look back-dated, and the backdating feature would carry no
        information at all.
        """
        rows = []
        for i in range(n_rows):
            inspected = dt.date(2026, int(self.rng.integers(1, 9)), int(self.rng.integers(1, 28)))
            signed = inspected + dt.timedelta(days=int(self.rng.integers(0, 11)))
            rows.append(
                {
                    "checkpoint": f"CP-{i:03d}",
                    "certificate_id": _make_identifier(self.rng, valid=True),
                    "inspected_on": inspected.isoformat(),
                    "signed_on": signed.isoformat(),
                    "result": "pass" if self.rng.random() > 0.12 else "remediate",
                }
            )
        if anomaly is None:
            return rows, None
        idx = int(self.rng.integers(0, n_rows))
        if anomaly == "checksum":
            rows[idx]["certificate_id"] = _make_identifier(self.rng, valid=False)
        elif anomaly == "backdating":
            # Signed months before the inspection it certifies.
            inspected = dt.date.fromisoformat(rows[idx]["inspected_on"])
            rows[idx]["signed_on"] = (inspected - dt.timedelta(days=int(self.rng.integers(30, 150)))).isoformat()
        return rows, idx

    def generate_of_kind(self, kind: str | None, n: int) -> list[Document]:
        """
        Generate n documents all of one anomaly kind (or all clean).

        The realistic corpus is deliberately imbalanced — anomalies are rare, and
        pretending otherwise would flatter any detector. For *training* a
        detector on a specific task, though, a balanced sample is what is needed.
        Keeping the two separate is the honest arrangement: train balanced,
        report on the realistic mix.
        """
        docs: list[Document] = []
        payroll_kinds = {"arithmetic", "overtime", "outlier"}
        for d in range(n):
            site = SITES[int(self.rng.integers(0, len(SITES)))]
            period = f"2026-{int(self.rng.integers(1, 9)):02d}"
            n_rows = int(self.rng.integers(8, 40))
            if kind is None:
                use_payroll = bool(self.rng.random() < 0.5)
            else:
                use_payroll = kind in payroll_kinds

            if use_payroll:
                rows, row_idx = self._payroll(site, n_rows, kind)
                record_type = "payroll_register"
            else:
                rows, row_idx = self._inspection(n_rows, kind)
                record_type = "safety_inspection"

            docs.append(
                Document(
                    doc_id=f"{kind or 'clean'}-{d:06d}",
                    record_type=record_type,
                    site=site,
                    period=period,
                    rows=rows,
                    label=0 if kind is None else 1,
                    anomaly_kind=kind,
                    anomaly_row=row_idx,
                )
            )
        return docs

    # -- corpus -----------------------------------------------------------
    def generate(self, n_docs: int = 50_000) -> list[Document]:
        docs: list[Document] = []
        for d in range(n_docs):
            record_type = RECORD_TYPES[int(self.rng.integers(0, len(RECORD_TYPES)))]
            site = SITES[int(self.rng.integers(0, len(SITES)))]
            period = f"2026-{int(self.rng.integers(1, 9)):02d}"
            is_anomalous = self.rng.random() < self.anomaly_rate
            kind = (
                ANOMALY_KINDS[int(self.rng.integers(0, len(ANOMALY_KINDS)))]
                if is_anomalous
                else None
            )
            n_rows = int(self.rng.integers(8, 40))

            if record_type == "payroll_register":
                if kind in ("checksum", "backdating"):
                    kind = "arithmetic"  # keep the anomaly applicable to the body
                rows, row_idx = self._payroll(site, n_rows, kind)
            else:
                if kind in ("arithmetic", "overtime", "outlier"):
                    kind = "checksum"
                rows, row_idx = self._inspection(n_rows, kind)

            docs.append(
                Document(
                    doc_id=f"doc-{d:06d}",
                    record_type=record_type,
                    site=site,
                    period=period,
                    rows=rows,
                    label=1 if kind else 0,
                    anomaly_kind=kind,
                    anomaly_row=row_idx,
                )
            )
        return docs


# --------------------------------------------------------------------------
# Feature extraction — runs inside the factory; only the output ever leaves
# --------------------------------------------------------------------------
FEATURE_NAMES = [
    "arith_max_residual",      # worst mismatch between a stated total and its parts
    "arith_mean_residual",
    "arith_frac_mismatched",
    "ot_max_hours",            # overtime pressure
    "ot_frac_over_legal",
    "ot_mean_hours",
    "checksum_frac_failed",    # certificate identifier validity
    "date_frac_backdated",     # signed before inspected
    "date_span_days",
    "val_max_zscore",          # distance from this site's own normal
    "val_mean_zscore",
    "val_skew",
    "row_count_z",
    "dup_ref_frac",
    "round_number_frac",       # suspiciously round values
    "digit_benford_dev",       # first-digit deviation from Benford's law
]
N_FEATURES = len(FEATURE_NAMES)


def extract_features(doc: Document, site_mean: float = BASE_WAGE_BDT) -> np.ndarray:
    """
    Turn one document into a fixed-length numeric vector.

    Note what is not in here: no worker reference, no certificate number, no
    date, no site name. The features are all *relative* quantities, which is
    what makes it defensible to share a model trained on them.
    """
    f = np.zeros(N_FEATURES, dtype=np.float64)
    rows = doc.rows
    n = max(1, len(rows))

    if "net_pay_bdt" in rows[0]:
        residuals, ot, values = [], [], []
        for r in rows:
            expected = r["basic_bdt"] + r["ot_pay_bdt"] - r["deductions_bdt"]
            denom = max(1.0, abs(expected))
            residuals.append(abs(r["net_pay_bdt"] - expected) / denom)
            ot.append(r["ot_hours"])
            values.append(r["basic_bdt"])
        residuals_a, ot_a, values_a = np.array(residuals), np.array(ot), np.array(values)
        f[0] = residuals_a.max()
        f[1] = residuals_a.mean()
        f[2] = float((residuals_a > 1e-6).mean())
        f[3] = ot_a.max() / LEGAL_OT_HOURS
        f[4] = float((ot_a > LEGAL_OT_HOURS).mean())
        f[5] = ot_a.mean() / LEGAL_OT_HOURS
        z = (values_a - site_mean) / max(1.0, site_mean * 0.08)
        f[9] = float(np.abs(z).max())
        f[10] = float(np.abs(z).mean())
        f[11] = float(((z - z.mean()) ** 3).mean() / max(1e-9, z.std() ** 3))
        f[14] = float(np.mean([abs(v - round(v, -2)) < 1e-9 for v in values_a]))
        first = np.array([int(str(abs(int(v)))[0]) for v in values_a if abs(v) >= 1])
        if len(first):
            observed = np.array([(first == d).mean() for d in range(1, 10)])
            benford = np.log10(1 + 1 / np.arange(1, 10))
            f[15] = float(np.abs(observed - benford).sum())
    else:
        failed = [not _checksum_ok(r["certificate_id"]) for r in rows]
        f[6] = float(np.mean(failed))
        backdated = [r["signed_on"] < r["inspected_on"] for r in rows]
        f[7] = float(np.mean(backdated))
        spans = [
            (dt.date.fromisoformat(r["signed_on"]) - dt.date.fromisoformat(r["inspected_on"])).days
            for r in rows
        ]
        # Mean signing delay in months. A back-dated row drags this negative,
        # and date_frac_backdated above already flags that a row is inverted.
        f[8] = float(np.mean(spans)) / 30.0
        refs = [r["checkpoint"] for r in rows]
        f[13] = 1.0 - len(set(refs)) / n

    f[12] = (len(rows) - 24) / 16.0
    return f


def build_dataset(docs: list[Document]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Feature matrix, labels, and the anomaly kind per document."""
    X = np.stack([extract_features(d) for d in docs])
    y = np.array([d.label for d in docs], dtype=np.int64)
    kinds = [d.anomaly_kind or "clean" for d in docs]
    return X, y, kinds


def main(n_docs: int = 50_000, out: str = "corpus") -> None:
    gen = DocumentGenerator()
    docs = gen.generate(n_docs)
    X, y, kinds = build_dataset(docs)

    out_dir = Path(__file__).parent / out
    out_dir.mkdir(exist_ok=True)
    np.save(out_dir / "features.npy", X)
    np.save(out_dir / "labels.npy", y)
    with open(out_dir / "ground_truth.json", "w") as fh:
        json.dump(
            {
                "n_documents": len(docs),
                "n_anomalous": int(y.sum()),
                "anomaly_rate": float(y.mean()),
                "feature_names": FEATURE_NAMES,
                "by_kind": {k: kinds.count(k) for k in set(kinds)},
                "note": "Invented data. No real factory, worker or document is represented.",
            },
            fh,
            indent=2,
        )
    print(f"{len(docs):,} documents, {int(y.sum()):,} anomalous ({y.mean():.2%})")
    for k in sorted(set(kinds)):
        print(f"  {k:<12} {kinds.count(k):>7,}")
    print(f"wrote {out_dir}")


if __name__ == "__main__":
    main()
