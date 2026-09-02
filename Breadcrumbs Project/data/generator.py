"""
Core streaming corpus generator engine and compatibility adapter layer (§8, §9).

Implements:
- StreamingCorpusGenerator: Streams millions of documents into sharded .jsonl.gz files
  organized under documents/site=<site>/wave=<n>/
- Full metadata output: manifest.json, ground_truth.json, adversary_trace.json, stats.json
- Backward-compatible Document and DocumentGenerator adapter layer.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .adversary.trace import AdversaryTraceManager
from .anomalies.injector import AnomalyInjector
from .anomalies.taxonomy import (
    ANOMALY_KINDS,
    RECORD_ANOMALY_COMPATIBILITY,
    WAVE_FOCUS_KINDS,
)
from .benchmarks import BenchmarkGenerator
from .config import CorpusConfig
from .io_utils import (
    write_canonical_json,
    write_jsonl_gz,
    write_parquet,
)
from .messiness import MessinessEngine
from .partition import FederatedPartitioner
from .records import (
    generate_chemical_records,
    generate_maintenance_records,
    generate_payroll_records,
    generate_production_records,
    generate_safety_records,
)
from .sites import SITE_KEYS, SITE_PROFILES, SiteProfile
from .timeline import PeriodInfo, generate_timeline


@dataclass
class Document:
    """Canonical document representation with complete ground truth metadata."""

    doc_id: str
    record_type: str        # payroll_register, safety_inspection, chemical_inventory, machine_maintenance, production_output
    site: str               # "gazipur", "ashulia", "narayanganj", "savar", "chattogram", "mirpur"
    period: str             # "YYYY-MM"
    rows: list[dict[str, Any]]
    label: int              # 0 clean, 1 anomalous
    anomaly_kind: str | None = None
    anomaly_row: int | None = None
    severity: float = 0.0
    site_key: str = ""
    wave: int = 1
    is_withheld: bool = False
    version: int = 1

    def __post_init__(self):
        if not self.site_key:
            self.site_key = self.site.lower()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict matching serialization format."""
        return {
            "doc_id": self.doc_id,
            "record_type": self.record_type,
            "site": self.site,
            "period": self.period,
            "rows": self.rows,
            "label": self.label,
            "anomaly_kind": self.anomaly_kind,
            "anomaly_row": self.anomaly_row,
            "severity": round(self.severity, 4),
            "wave": self.wave,
            "is_withheld": self.is_withheld,
            "version": self.version,
        }


class StreamingCorpusGenerator:
    """High-performance deterministic streaming generator for large-scale corpora."""

    def __init__(self, config: CorpusConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        self.partitioner = FederatedPartitioner(seed=config.seed, alpha=config.dirichlet_alpha)
        self.adversary_manager = AdversaryTraceManager(config)
        self.messiness = MessinessEngine(base_rate=config.messiness_rate)
        self.timeline = generate_timeline(config.start_period, config.end_period)

    def _sample_document_rows(
        self,
        record_type: str,
        site: SiteProfile,
        period_info: PeriodInfo,
        rng: np.random.Generator,
    ) -> list[dict[str, Any]]:
        """Dispatch row generation to the appropriate domain module."""
        if record_type == "payroll_register":
            # Scale row count by site size (approx 20 to 60 sample rows per document)
            n_rows = int(rng.integers(15, 50))
            return generate_payroll_records(site, period_info, n_rows, self.messiness, rng)
        elif record_type == "safety_inspection":
            n_rows = int(rng.integers(10, 30))
            return generate_safety_records(site, period_info, n_rows, self.messiness, rng)
        elif record_type == "chemical_inventory":
            n_rows = int(rng.integers(8, 25))
            return generate_chemical_records(site, period_info, n_rows, self.messiness, rng)
        elif record_type == "machine_maintenance":
            n_rows = int(rng.integers(12, 35))
            return generate_maintenance_records(site, period_info, n_rows, self.messiness, rng)
        elif record_type == "production_output":
            n_rows = int(rng.integers(15, 40))
            return generate_production_records(site, period_info, n_rows, self.messiness, rng)
        else:
            raise ValueError(f"Unknown record type: {record_type}")

    def generate_single_document(
        self,
        doc_idx: int,
        site_key: str,
        period_info: PeriodInfo,
        forced_anomaly: str | None = None,
        force_clean: bool = False,
    ) -> Document:
        """Deterministically generate a single Document instance."""
        site = SITE_PROFILES[site_key]
        record_type = self.partitioner.sample_record_type(site_key, self.rng)
        rows = self._sample_document_rows(record_type, site, period_info, self.rng)

        # Anomaly evaluation
        if force_clean:
            is_anomalous = False
        elif forced_anomaly is not None:
            is_anomalous = True
        elif self.config.balanced_mode:
            is_anomalous = bool(doc_idx % 2 == 1)
        else:
            is_anomalous = float(self.rng.random()) < self.config.anomaly_rate

        anomaly_kind: str | None = None
        anomaly_row: int | None = None
        severity = 0.0

        if is_anomalous:
            if forced_anomaly:
                anomaly_kind = forced_anomaly
            else:
                # Select anomaly kind matching wave focus or recurrence
                if period_info.is_recurrence_window and self.config.include_recurrence and float(self.rng.random()) < self.config.recurrence_rate * 5:
                    eligible_kinds = WAVE_FOCUS_KINDS[1]  # Recurrence of Wave 1
                else:
                    eligible_kinds = WAVE_FOCUS_KINDS.get(period_info.wave, ("arithmetic", "outlier"))

                compatible = [k for k in eligible_kinds if k in RECORD_ANOMALY_COMPATIBILITY.get(record_type, ())]
                if not compatible:
                    compatible = list(RECORD_ANOMALY_COMPATIBILITY.get(record_type, ("arithmetic",)))

                anomaly_kind = self.partitioner.sample_anomaly_kind(site_key, compatible, self.rng)

            severity = float(self.rng.uniform(self.config.severity_min, self.config.severity_max))
            rows, anomaly_row, meta = AnomalyInjector.inject(
                record_type, rows, anomaly_kind, severity, site, period_info, self.rng
            )

        doc_id = f"doc-{site_key[:3]}-w{period_info.wave}-{doc_idx:06d}"

        return Document(
            doc_id=doc_id,
            record_type=record_type,
            site=site_key,
            period=period_info.period,
            rows=rows,
            label=1 if is_anomalous else 0,
            anomaly_kind=anomaly_kind,
            anomaly_row=anomaly_row,
            severity=severity,
            site_key=site_key,
            wave=period_info.wave,
            is_withheld=False,
            version=1,
        )

    def generate_corpus(self) -> dict[str, Any]:
        """
        Execute full corpus streaming generation:
        - Shards written under documents/site=<site>/wave=<n>/part-*.jsonl.gz
        - Held-out benchmarks and SHA-256 hashes written under benchmarks/
        - Ground truth, adversary trace, stats, and manifest emitted
        """
        start_time = time.time()
        out_path = Path(self.config.output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        docs_dir = out_path / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)

        total_target_docs = self.config.get_effective_doc_count()
        n_periods = len(self.timeline)
        docs_per_period = max(1, total_target_docs // n_periods)

        # Ground truth tracking & statistics accumulation
        ground_truth: dict[str, Any] = {
            "version": "1.0.0",
            "seed": self.config.seed,
            "total_documents": 0,
            "documents": {},
        }
        stats: dict[str, Any] = {
            "total_documents": 0,
            "total_anomalous": 0,
            "overall_anomaly_rate": 0.0,
            "by_site": {s: {"total": 0, "anomalous": 0, "by_kind": {}} for s in SITE_KEYS},
            "by_wave": {w: {"total": 0, "anomalous": 0, "by_kind": {}} for w in (1, 2, 3)},
            "by_record_type": {},
            "by_anomaly_kind": {k: 0 for k in ANOMALY_KINDS},
        }

        file_hashes: dict[str, str] = {}
        global_doc_idx = 0

        # Iterate chronologically over the 36-month timeline
        for p_info in self.timeline:
            period_docs: list[Document] = []

            for site_key in SITE_KEYS:
                site_weight = self.partitioner.site_profiles[site_key].volume_weight
                site_period_doc_count = max(1, int(round(docs_per_period * site_weight)))

                site_wave_dir = docs_dir / f"site={site_key}" / f"wave={p_info.wave}"
                site_wave_dir.mkdir(parents=True, exist_ok=True)

                current_shard_docs: list[dict[str, Any]] = []

                for _ in range(site_period_doc_count):
                    global_doc_idx += 1
                    doc = self.generate_single_document(global_doc_idx, site_key, p_info)
                    period_docs.append(doc)

                    # Update stats
                    stats["total_documents"] += 1
                    stats["by_site"][site_key]["total"] += 1
                    stats["by_wave"][p_info.wave]["total"] += 1
                    stats["by_record_type"][doc.record_type] = stats["by_record_type"].get(doc.record_type, 0) + 1

                    if doc.label == 1:
                        stats["total_anomalous"] += 1
                        stats["by_site"][site_key]["anomalous"] += 1
                        stats["by_wave"][p_info.wave]["anomalous"] += 1
                        if doc.anomaly_kind:
                            stats["by_anomaly_kind"][doc.anomaly_kind] = stats["by_anomaly_kind"].get(doc.anomaly_kind, 0) + 1
                            site_kinds = stats["by_site"][site_key]["by_kind"]
                            site_kinds[doc.anomaly_kind] = site_kinds.get(doc.anomaly_kind, 0) + 1
                            wave_kinds = stats["by_wave"][p_info.wave]["by_kind"]
                            wave_kinds[doc.anomaly_kind] = wave_kinds.get(doc.anomaly_kind, 0) + 1

                    # Record ground truth
                    ground_truth["documents"][doc.doc_id] = {
                        "label": doc.label,
                        "anomaly_kind": doc.anomaly_kind,
                        "anomaly_row": doc.anomaly_row,
                        "severity": round(doc.severity, 4),
                        "record_type": doc.record_type,
                        "site": doc.site,
                        "period": doc.period,
                        "wave": doc.wave,
                        "is_withheld": doc.is_withheld,
                    }

                    current_shard_docs.append(doc.to_dict())

                # Write site-wave shard
                shard_filename = f"part-{p_info.period}-{site_key}.jsonl.gz"
                shard_path = site_wave_dir / shard_filename
                rel_path = str(shard_path.relative_to(out_path))
                h = write_jsonl_gz(shard_path, current_shard_docs)
                file_hashes[rel_path] = h

                if self.config.output_parquet:
                    parquet_filename = f"part-{p_info.period}-{site_key}.parquet"
                    parquet_path = site_wave_dir / parquet_filename
                    write_parquet(parquet_path, current_shard_docs)

            # Process timeline adversary attacks for this period
            extra_attack_docs = self.adversary_manager.generate_timeline_attacks(
                p_info, period_docs, self.rng
            )
            # Sync any withheld flags back to ground_truth dictionary
            for doc in period_docs:
                if doc.is_withheld and doc.doc_id in ground_truth["documents"]:
                    ground_truth["documents"][doc.doc_id]["is_withheld"] = True

            for extra_doc in extra_attack_docs:
                ground_truth["documents"][extra_doc.doc_id] = {
                    "label": extra_doc.label,
                    "anomaly_kind": extra_doc.anomaly_kind,
                    "anomaly_row": extra_doc.anomaly_row,
                    "severity": round(extra_doc.severity, 4),
                    "record_type": extra_doc.record_type,
                    "site": extra_doc.site,
                    "period": extra_doc.period,
                    "wave": extra_doc.wave,
                    "is_withheld": False,
                    "version": extra_doc.version,
                }

        ground_truth["total_documents"] = stats["total_documents"]
        stats["overall_anomaly_rate"] = round(stats["total_anomalous"] / max(1, stats["total_documents"]), 4)

        # Write benchmarks
        bench_gen = BenchmarkGenerator(self.config, self.partitioner)
        bench_hashes = bench_gen.generate_all_benchmarks(out_path)
        for b_name, b_hash in bench_hashes.items():
            file_hashes[f"benchmarks/{b_name}"] = b_hash

        # Write ground_truth.json
        gt_path = out_path / "ground_truth.json"
        h_gt = write_canonical_json(gt_path, ground_truth)
        file_hashes["ground_truth.json"] = h_gt

        # Write adversary_trace.json
        adv_path = out_path / "adversary_trace.json"
        trace_payload = {
            "version": "1.0.0",
            "seed": self.config.seed,
            "total_events": len(self.adversary_manager.events),
            "events": self.adversary_manager.to_list(),
        }
        h_adv = write_canonical_json(adv_path, trace_payload)
        file_hashes["adversary_trace.json"] = h_adv

        # Write stats.json
        stats_path = out_path / "stats.json"
        h_stats = write_canonical_json(stats_path, stats)
        file_hashes["stats.json"] = h_stats

        # Write manifest.json with normalized config representation
        manifest_path = out_path / "manifest.json"
        norm_config = dict(self.config.to_dict())
        norm_config["output_dir"] = "corpus"
        manifest_payload = {
            "generator_version": "1.0.0",
            "config": norm_config,
            "partition": self.partitioner.to_manifest_dict(),
            "file_hashes": file_hashes,
        }
        write_canonical_json(manifest_path, manifest_payload)

        # Ensure data_card.md is present in output
        data_card_source = Path(__file__).parent / "data_card.md"
        if data_card_source.exists():
            shutil.copy(data_card_source, out_path / "data_card.md")

        elapsed = time.time() - start_time
        return {
            "total_documents": stats["total_documents"],
            "total_anomalous": stats["total_anomalous"],
            "anomaly_rate": stats["overall_anomaly_rate"],
            "elapsed_seconds": round(elapsed, 2),
            "output_dir": str(out_path),
        }


# ---------------------------------------------------------------------------
# Backward compatibility adapter interface (§9)
# ---------------------------------------------------------------------------

class DocumentGenerator:
    """
    Backward-compatible adapter matching the existing repository's API contract.

    Supports:
        DocumentGenerator(seed: int = 7, anomaly_rate: float = 0.04)
        generate(n_docs: int) -> list[Document]
        generate_of_kind(kind: str | None, n: int) -> list[Document]
    """

    def __init__(self, seed: int = 7, anomaly_rate: float = 0.04):
        self.config = CorpusConfig(seed=seed, anomaly_rate=anomaly_rate)
        self.generator = StreamingCorpusGenerator(self.config)
        self.rng = np.random.default_rng(seed)

    def generate(self, n_docs: int = 50_000) -> list[Document]:
        """Generate a list of in-memory Document objects matching the target count."""
        docs: list[Document] = []
        timeline = self.generator.timeline

        for d in range(n_docs):
            site_key = SITE_KEYS[int(self.rng.integers(0, len(SITE_KEYS)))]
            p_info = timeline[int(self.rng.integers(0, len(timeline)))]
            doc = self.generator.generate_single_document(d + 1, site_key, p_info)
            docs.append(doc)

        return docs

    def generate_of_kind(self, kind: str | None, n: int) -> list[Document]:
        """Generate n documents all of one anomaly kind (or all clean)."""
        docs: list[Document] = []
        timeline = self.generator.timeline

        for d in range(n):
            site_key = SITE_KEYS[int(self.rng.integers(0, len(SITE_KEYS)))]
            p_info = timeline[int(self.rng.integers(0, len(timeline)))]
            if kind is None or kind == "clean":
                doc = self.generator.generate_single_document(d + 1, site_key, p_info, force_clean=True)
            else:
                doc = self.generator.generate_single_document(d + 1, site_key, p_info, forced_anomaly=kind)
            docs.append(doc)

        return docs
