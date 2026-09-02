"""
Configuration schema and parameters for the Breadcrumbs Synthetic Corpus Generator.

Every knob is defined with explicit defaults and documentation on why the value was chosen.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CorpusConfig:
    """
    Introspectable, fully deterministic configuration for the synthetic corpus.

    All knobs controlling scale, time waves, noise, anomaly injection, Dirichlet partition,
    and the adversary trace are declared here.
    """

    # Core generation & determinism
    seed: int = 7
    scale: str = "small"  # "small" (~20k docs), "medium" (~200k docs), "large" (~1M docs)
    total_docs: int | None = None  # Explicit override if non-None
    output_dir: str = "corpus"
    output_parquet: bool = False
    shard_size: int = 1000  # Number of documents per .jsonl.gz shard file

    # Time boundaries (36 monthly periods across 3 waves)
    start_period: str = "2025-01"
    end_period: str = "2027-12"

    # Detector axis: anomaly parameters
    anomaly_rate: float = 0.04  # 4% base anomaly rate across the realistic corpus
    severity_min: float = 0.10  # Minimum continuous anomaly severity (subtle, 1-3% error)
    severity_max: float = 1.00  # Maximum continuous anomaly severity (blatant, 20-50% error)
    balanced_mode: bool = False  # If True, generates balanced classes for training detector
    include_recurrence: bool = True  # Reintroduces Wave 1 anomalies late in Wave 3
    recurrence_rate: float = 0.015  # Rate of recurring Wave 1 anomalies in 2027 Q4

    # Federated partition parameters
    dirichlet_alpha: float = 0.60  # Dirichlet concentration parameter for non-IID site partition

    # Realism & Noise parameters
    messiness_rate: float = 0.15  # Base probability of field messiness / alternate formatting

    # Ledger axis: Adversary trace parameters
    attack_rate: float = 0.05  # Base probability of an adversary attack event per period/site
    attack_difficulty: float = 0.50  # 0.0 (obvious) to 1.0 (careful adversary hiding traces)
    benign_amendment_ratio: float = 0.35  # Fraction of edits/amendments that are benign corrections

    # Benchmarks
    benchmark_size_per_wave: int = 1000  # Held-out documents per wave benchmark
    cross_wave_benchmark_size: int = 2000  # Held-out documents for cross-wave benchmark

    def get_effective_doc_count(self) -> int:
        """Resolve total documents based on scale or explicit override."""
        if self.total_docs is not None:
            return self.total_docs
        scale_map = {
            "small": 20_000,
            "medium": 200_000,
            "large": 1_000_000,
        }
        return scale_map.get(self.scale.lower(), 20_000)

    def to_dict(self) -> dict[str, Any]:
        """Canonical dictionary representation for manifest serialization."""
        return dataclasses.asdict(self)

    def print_summary(self) -> None:
        """Display effective configuration at generator startup."""
        effective_docs = self.get_effective_doc_count()
        print("=" * 60)
        print("Breadcrumbs Synthetic Corpus Generator")
        print("=" * 60)
        print(f"Seed:               {self.seed}")
        print(f"Scale:              {self.scale} ({effective_docs:,} total documents)")
        print(f"Time Range:         {self.start_period} -> {self.end_period} (36 months, 3 waves)")
        print(f"Anomaly Rate:       {self.anomaly_rate:.2%}")
        print(f"Severity Range:     [{self.severity_min:.2f}, {self.severity_max:.2f}]")
        print(f"Dirichlet Alpha:    {self.dirichlet_alpha}")
        print(f"Adversary Attacks:  Rate={self.attack_rate:.2%}, Difficulty={self.attack_difficulty:.2f}")
        print(f"Output Directory:   {self.output_dir}")
        print(f"Parquet Output:     {'Enabled' if self.output_parquet else 'Disabled'}")
        print("=" * 60)
