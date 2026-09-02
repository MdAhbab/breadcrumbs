"""
Federated Non-IID Dirichlet Partition (§5).

Partitions the corpus across the 6 factory sites non-identically:
- Dirichlet distribution with alpha = 0.6 over the 9 anomaly kinds per site
- Volume scaling proportional to worker count
- Specialized record-type mixes (e.g. Chattogram chemical dyeing, Narayanganj maintenance)
- Pure deterministic function of the base seed
- Serializable per-site assignment matrix for manifest.json
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .anomalies.taxonomy import ANOMALY_KINDS
from .sites import RECORD_TYPES, SITE_KEYS, SITE_PROFILES


@dataclass(frozen=True)
class SitePartitionProfile:
    """Per-site federated distribution profile."""

    site_key: str
    worker_count: int
    volume_weight: float
    record_type_distribution: dict[str, float]
    anomaly_kind_distribution: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_key": self.site_key,
            "worker_count": self.worker_count,
            "volume_weight": round(self.volume_weight, 4),
            "record_type_distribution": {k: round(v, 4) for k, v in self.record_type_distribution.items()},
            "anomaly_kind_distribution": {k: round(v, 4) for k, v in self.anomaly_kind_distribution.items()},
        }


class FederatedPartitioner:
    """Generates deterministic non-IID partition weights across sites."""

    def __init__(self, seed: int = 7, alpha: float = 0.60):
        self.seed = seed
        self.alpha = alpha
        self.rng = np.random.default_rng(seed)
        self.site_profiles: dict[str, SitePartitionProfile] = self._build_partitions()

    def _build_partitions(self) -> dict[str, SitePartitionProfile]:
        profiles: dict[str, SitePartitionProfile] = {}
        total_workers = sum(p.worker_count for p in SITE_PROFILES.values())

        # For each site, sample a Dirichlet vector over the 9 anomaly kinds
        n_kinds = len(ANOMALY_KINDS)
        alpha_vec = np.full(n_kinds, self.alpha, dtype=np.float64)

        for site_key in SITE_KEYS:
            site = SITE_PROFILES[site_key]
            vol_weight = site.worker_count / float(total_workers)

            # Sample Dirichlet weights for anomaly kinds
            dirichlet_sample = self.rng.dirichlet(alpha_vec)
            anomaly_dist = {
                k: float(dirichlet_sample[i]) for i, k in enumerate(ANOMALY_KINDS)
            }

            # Normalize site-specific record type weights
            raw_rec_weights = [site.record_type_weights.get(rt, 1.0) for rt in RECORD_TYPES]
            tot_rec = sum(raw_rec_weights)
            rec_dist = {
                rt: float(raw_rec_weights[i] / tot_rec) for i, rt in enumerate(RECORD_TYPES)
            }

            profiles[site_key] = SitePartitionProfile(
                site_key=site_key,
                worker_count=site.worker_count,
                volume_weight=vol_weight,
                record_type_distribution=rec_dist,
                anomaly_kind_distribution=anomaly_dist,
            )

        return profiles

    def sample_record_type(self, site_key: str, rng: np.random.Generator) -> str:
        """Sample a record type for a given site according to its profile."""
        dist = self.site_profiles[site_key].record_type_distribution
        types = list(dist.keys())
        probs = [dist[t] for t in types]
        return str(rng.choice(types, p=probs))

    def sample_anomaly_kind(
        self,
        site_key: str,
        eligible_kinds: tuple[str, ...] | list[str],
        rng: np.random.Generator,
    ) -> str:
        """Sample an anomaly kind for a given site conditioned on candidate kinds."""
        full_dist = self.site_profiles[site_key].anomaly_kind_distribution
        probs = [max(1e-6, full_dist.get(k, 0.0)) for k in eligible_kinds]
        tot = sum(probs)
        norm_probs = [p / tot for p in probs]
        return str(rng.choice(list(eligible_kinds), p=norm_probs))

    def to_manifest_dict(self) -> dict[str, Any]:
        """Matrix format suitable for inclusion in manifest.json."""
        return {
            "alpha": self.alpha,
            "sites": {k: p.to_dict() for k, p in self.site_profiles.items()},
        }
