"""
Benchmark dataset generator (§6).

Emits held-out benchmark datasets:
- wave1.jsonl.gz: Held-out benchmark drawn from Wave 1 end distribution
- wave2.jsonl.gz: Held-out benchmark drawn from Wave 2 end distribution
- wave3.jsonl.gz: Held-out benchmark drawn from Wave 3 end distribution
- cross_wave.jsonl.gz: Comprehensive benchmark spanning all waves and recurrence
- hashes.json: Canonically serialized SHA-256 digests
All benchmark document IDs are strictly disjoint from training shards.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .anomalies.injector import AnomalyInjector
from .anomalies.taxonomy import RECORD_ANOMALY_COMPATIBILITY, WAVE_FOCUS_KINDS
from .config import CorpusConfig
from .io_utils import write_canonical_json, write_jsonl_gz
from .messiness import MessinessEngine
from .partition import FederatedPartitioner
from .records import (
    generate_chemical_records,
    generate_maintenance_records,
    generate_payroll_records,
    generate_production_records,
    generate_safety_records,
)
from .sites import SITE_KEYS, SITE_PROFILES
from .timeline import PeriodInfo, generate_timeline


class BenchmarkGenerator:
    """Produces held-out benchmark test sets and their canonical cryptographic hashes."""

    def __init__(self, config: CorpusConfig, partitioner: FederatedPartitioner):
        self.config = config
        self.partitioner = partitioner
        self.messiness = MessinessEngine(base_rate=config.messiness_rate)
        # Dedicated deterministic RNG branch for benchmarks
        self.rng = np.random.default_rng(config.seed + 999_999)

    def _generate_doc(
        self,
        doc_id: str,
        site_key: str,
        period_info: PeriodInfo,
        forced_anomaly: bool,
    ) -> dict[str, Any]:
        """Generate a single benchmark document."""
        site = SITE_PROFILES[site_key]
        record_type = self.partitioner.sample_record_type(site_key, self.rng)

        # Determine row count based on record type
        if record_type == "payroll_register":
            n_rows = int(self.rng.integers(15, 45))
            rows = generate_payroll_records(site, period_info, n_rows, self.messiness, self.rng)
        elif record_type == "safety_inspection":
            n_rows = int(self.rng.integers(10, 30))
            rows = generate_safety_records(site, period_info, n_rows, self.messiness, self.rng)
        elif record_type == "chemical_inventory":
            n_rows = int(self.rng.integers(8, 25))
            rows = generate_chemical_records(site, period_info, n_rows, self.messiness, self.rng)
        elif record_type == "machine_maintenance":
            n_rows = int(self.rng.integers(12, 35))
            rows = generate_maintenance_records(site, period_info, n_rows, self.messiness, self.rng)
        else:  # production_output
            n_rows = int(self.rng.integers(15, 40))
            rows = generate_production_records(site, period_info, n_rows, self.messiness, self.rng)

        is_anomalous = forced_anomaly or (float(self.rng.random()) < self.config.anomaly_rate)
        anomaly_kind = None
        anomaly_row = None
        severity = 0.0

        if is_anomalous:
            # Benchmark reflects wave end distribution
            wave_kinds = WAVE_FOCUS_KINDS.get(period_info.wave, ("arithmetic", "outlier"))
            eligible = [k for k in wave_kinds if k in RECORD_ANOMALY_COMPATIBILITY.get(record_type, ())]
            if not eligible:
                eligible = list(RECORD_ANOMALY_COMPATIBILITY.get(record_type, ("arithmetic",)))

            anomaly_kind = self.partitioner.sample_anomaly_kind(site_key, eligible, self.rng)
            severity = float(self.rng.uniform(self.config.severity_min, self.config.severity_max))
            rows, anomaly_row, meta = AnomalyInjector.inject(
                record_type, rows, anomaly_kind, severity, site, period_info, self.rng
            )

        return {
            "doc_id": doc_id,
            "record_type": record_type,
            "site": site_key,
            "period": period_info.period,
            "rows": rows,
            "label": 1 if is_anomalous else 0,
            "anomaly_kind": anomaly_kind,
            "anomaly_row": anomaly_row,
            "severity": round(severity, 4),
            "wave": period_info.wave,
            "is_benchmark": True,
        }

    def generate_all_benchmarks(self, output_dir: Path) -> dict[str, str]:
        """Generate Wave 1-3 and cross-wave benchmarks, writing .jsonl.gz and hashes.json."""
        bench_dir = output_dir / "benchmarks"
        bench_dir.mkdir(parents=True, exist_ok=True)

        timeline = generate_timeline(self.config.start_period, self.config.end_period)
        wave_periods = {
            1: [p for p in timeline if p.wave == 1 and p.month in (10, 11, 12)],  # End of Wave 1
            2: [p for p in timeline if p.wave == 2 and p.month in (10, 11, 12)],  # End of Wave 2
            3: [p for p in timeline if p.wave == 3 and p.month in (10, 11, 12)],  # End of Wave 3
        }

        hashes: dict[str, str] = {}
        all_cross_docs: list[dict[str, Any]] = []

        # Generate Wave 1, 2, 3 benchmark sets
        for wave_num in (1, 2, 3):
            wave_docs: list[dict[str, Any]] = []
            periods = wave_periods[wave_num]
            target_count = self.config.benchmark_size_per_wave

            for idx in range(target_count):
                doc_id = f"bench-w{wave_num}-{idx:06d}"
                site_key = SITE_KEYS[int(self.rng.integers(0, len(SITE_KEYS)))]
                p_info = periods[int(self.rng.integers(0, len(periods)))]

                # Ensure balanced 50/50 test set for rigorous benchmark evaluation
                forced_anomaly = bool(idx % 2 == 1)
                doc = self._generate_doc(doc_id, site_key, p_info, forced_anomaly)
                wave_docs.append(doc)
                if idx < (self.config.cross_wave_benchmark_size // 3):
                    all_cross_docs.append(dict(doc, doc_id=f"bench-cross-w{wave_num}-{idx:06d}"))

            wave_file = bench_dir / f"wave{wave_num}.jsonl.gz"
            h = write_jsonl_gz(wave_file, wave_docs)
            hashes[f"wave{wave_num}.jsonl.gz"] = h

        # Generate cross-wave benchmark
        cross_file = bench_dir / "cross_wave.jsonl.gz"
        h_cross = write_jsonl_gz(cross_file, all_cross_docs)
        hashes["cross_wave.jsonl.gz"] = h_cross

        # Write hashes.json
        write_canonical_json(bench_dir / "hashes.json", hashes)
        return hashes
