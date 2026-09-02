"""
Acceptance Test 5: The Dirichlet partition is reproducible and genuinely non-IID.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from data.config import CorpusConfig
from data.generator import StreamingCorpusGenerator
from data.partition import FederatedPartitioner
from data.sites import SITE_KEYS


def test_dirichlet_partition_is_reproducible_and_non_iid():
    """Verify reproducible Dirichlet partition with alpha=0.6 and assert non-IID divergence."""
    # 1. Verify partition reproducibility with identical seed
    part1 = FederatedPartitioner(seed=7, alpha=0.60)
    part2 = FederatedPartitioner(seed=7, alpha=0.60)

    dict1 = part1.to_manifest_dict()
    dict2 = part2.to_manifest_dict()
    assert dict1 == dict2, "Partitioner not reproducible with same seed"

    # 2. Verify non-IID nature: site distribution vectors must diverge
    site_vectors = []
    for site_key in SITE_KEYS:
        dist = part1.site_profiles[site_key].anomaly_kind_distribution
        vec = np.array([dist[k] for k in sorted(dist.keys())])
        site_vectors.append(vec)

    # Compute pairwise Total Variation (TV) distances across site pairs
    tv_distances = []
    n_sites = len(site_vectors)
    for i in range(n_sites):
        for j in range(i + 1, n_sites):
            tv = 0.5 * np.sum(np.abs(site_vectors[i] - site_vectors[j]))
            tv_distances.append(tv)

    mean_tv = float(np.mean(tv_distances))
    # Under alpha = 0.6 over 9 categories, mean TV distance between Dirichlet draws is typically > 0.35
    assert mean_tv > 0.20, f"Dirichlet distributions are too homogeneous (mean TV={mean_tv:.4f})"

    # 3. Verify manifest output in full generation
    with tempfile.TemporaryDirectory() as tmp:
        cfg = CorpusConfig(seed=7, scale="small", total_docs=500, output_dir=tmp)
        gen = StreamingCorpusGenerator(cfg)
        gen.generate_corpus()

        with open(Path(tmp) / "manifest.json") as fh:
            manifest = json.load(fh)

        assert "partition" in manifest
        assert manifest["partition"]["alpha"] == 0.60
        assert len(manifest["partition"]["sites"]) == len(SITE_KEYS)
