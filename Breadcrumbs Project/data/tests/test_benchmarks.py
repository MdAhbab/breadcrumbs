"""
Acceptance Test 6: Benchmarks are strictly disjoint from training shards by document ID.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from data.config import CorpusConfig
from data.generator import StreamingCorpusGenerator
from data.io_utils import read_jsonl_gz


def test_benchmarks_are_disjoint_from_training_shards():
    """Assert zero doc_id intersection between training shards and all held-out benchmark files."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = CorpusConfig(seed=7, scale="small", total_docs=600, output_dir=tmp)
        gen = StreamingCorpusGenerator(cfg)
        gen.generate_corpus()

        tmp_path = Path(tmp)

        # Collect all training shard document IDs
        training_doc_ids = set()
        for shard in tmp_path.glob("documents/**/*.jsonl.gz"):
            docs = read_jsonl_gz(shard)
            for d in docs:
                training_doc_ids.add(d["doc_id"])

        assert len(training_doc_ids) > 0, "No training documents found"

        # Collect all benchmark document IDs
        benchmark_files = list(tmp_path.glob("benchmarks/*.jsonl.gz"))
        assert len(benchmark_files) == 4, f"Expected 4 benchmark files, found {len(benchmark_files)}"

        benchmark_doc_ids = set()
        for b_file in benchmark_files:
            docs = read_jsonl_gz(b_file)
            for d in docs:
                benchmark_doc_ids.add(d["doc_id"])

        assert len(benchmark_doc_ids) > 0, "No benchmark documents found"

        # Assert strict empty intersection
        overlap = training_doc_ids.intersection(benchmark_doc_ids)
        assert len(overlap) == 0, f"Found {len(overlap)} overlapping doc_ids: {list(overlap)[:5]}"

        # Verify hashes.json exists and contains entries for all 4 benchmark files
        hashes_file = tmp_path / "benchmarks" / "hashes.json"
        assert hashes_file.exists()
        with open(hashes_file) as fh:
            hashes = json.load(fh)

        for b_name in ("wave1.jsonl.gz", "wave2.jsonl.gz", "wave3.jsonl.gz", "cross_wave.jsonl.gz"):
            assert b_name in hashes, f"Missing hash entry for {b_name}"
            assert len(hashes[b_name]) == 64, f"Invalid SHA-256 length for {b_name}"
