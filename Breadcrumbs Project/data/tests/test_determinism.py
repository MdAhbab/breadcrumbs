"""
Acceptance Test 1: Same seed twice -> identical file hashes for every output file.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from data.config import CorpusConfig
from data.generator import StreamingCorpusGenerator
from data.io_utils import calculate_sha256


def test_determinism_same_seed_produces_identical_hashes():
    """Verify that generating a corpus twice with seed=7 produces bit-identical outputs."""
    seed = 7
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        cfg1 = CorpusConfig(seed=seed, scale="small", total_docs=600, output_dir=tmp1)
        cfg2 = CorpusConfig(seed=seed, scale="small", total_docs=600, output_dir=tmp2)

        gen1 = StreamingCorpusGenerator(cfg1)
        gen1.generate_corpus()

        gen2 = StreamingCorpusGenerator(cfg2)
        gen2.generate_corpus()

        p1 = Path(tmp1)
        p2 = Path(tmp2)

        files1 = sorted([str(f.relative_to(p1)) for f in p1.rglob("*") if f.is_file()])
        files2 = sorted([str(f.relative_to(p2)) for f in p2.rglob("*") if f.is_file()])

        assert files1 == files2, f"File lists differ: {files1} != {files2}"
        assert len(files1) > 0, "No files generated"

        for rel_file in files1:
            h1 = calculate_sha256(p1 / rel_file)
            h2 = calculate_sha256(p2 / rel_file)
            assert h1 == h2, f"Hash mismatch in {rel_file}: {h1} != {h2}"
