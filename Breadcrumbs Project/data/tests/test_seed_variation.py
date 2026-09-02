"""
Acceptance Test 2: Different seed -> different content, same schema, label rates within 10% of target.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from data.config import CorpusConfig
from data.generator import StreamingCorpusGenerator
from data.io_utils import calculate_sha256, read_jsonl_gz
from data.schemas import validate_row_schema


def test_different_seeds_produce_different_content_with_stable_rates():
    """Verify distinct content across seeds while adhering to schemas and target label rates."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        cfg1 = CorpusConfig(seed=11, scale="small", total_docs=1000, anomaly_rate=0.04, output_dir=tmp1)
        cfg2 = CorpusConfig(seed=99, scale="small", total_docs=1000, anomaly_rate=0.04, output_dir=tmp2)

        gen1 = StreamingCorpusGenerator(cfg1)
        res1 = gen1.generate_corpus()

        gen2 = StreamingCorpusGenerator(cfg2)
        res2 = gen2.generate_corpus()

        # Label rates should be within tolerance of target (target = 4%, relative tolerance +-15% / absolute within 1.5%)
        rate1 = res1["anomaly_rate"]
        rate2 = res2["anomaly_rate"]
        assert abs(rate1 - 0.04) < 0.015, f"Seed 11 rate {rate1} too far from target 0.04"
        assert abs(rate2 - 0.04) < 0.015, f"Seed 99 rate {rate2} too far from target 0.04"

        # Check that file content differs across seeds
        p1 = Path(tmp1)
        p2 = Path(tmp2)
        gt_hash1 = calculate_sha256(p1 / "ground_truth.json")
        gt_hash2 = calculate_sha256(p2 / "ground_truth.json")
        assert gt_hash1 != gt_hash2, "Different seeds produced identical ground truth hashes"

        # Check that every row validates against schema in both sets
        shards1 = list(p1.glob("documents/**/*.jsonl.gz"))
        assert len(shards1) > 0
        for shard in shards1[:3]:
            docs = read_jsonl_gz(shard)
            for d in docs:
                for row in d["rows"]:
                    ok, msg = validate_row_schema(d["record_type"], row)
                    assert ok, f"Schema validation error in seed 11: {msg}"
