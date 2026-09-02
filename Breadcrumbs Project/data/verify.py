"""
Determinism verification self-test utility (§9, §11).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .config import CorpusConfig
from .generator import StreamingCorpusGenerator
from .io_utils import calculate_sha256


def verify_determinism(seed: int = 7) -> bool:
    """
    Generate a small corpus twice in separate temporary directories and verify
    that all file hashes match byte-for-byte.
    """
    print("Running determinism verification self-test...")
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        cfg1 = CorpusConfig(seed=seed, scale="small", total_docs=300, output_dir=tmp1)
        cfg2 = CorpusConfig(seed=seed, scale="small", total_docs=300, output_dir=tmp2)

        gen1 = StreamingCorpusGenerator(cfg1)
        gen1.generate_corpus()

        gen2 = StreamingCorpusGenerator(cfg2)
        gen2.generate_corpus()

        p1 = Path(tmp1)
        p2 = Path(tmp2)

        files1 = sorted([str(f.relative_to(p1)) for f in p1.rglob("*") if f.is_file()])
        files2 = sorted([str(f.relative_to(p2)) for f in p2.rglob("*") if f.is_file()])

        if files1 != files2:
            print(f"[FAIL] Output file list mismatch:\n  Run1: {files1}\n  Run2: {files2}")
            return False

        mismatches = []
        for rel_file in files1:
            h1 = calculate_sha256(p1 / rel_file)
            h2 = calculate_sha256(p2 / rel_file)
            if h1 != h2:
                mismatches.append((rel_file, h1, h2))

        if mismatches:
            print(f"[FAIL] Byte mismatch in {len(mismatches)} files:")
            for mf, h1, h2 in mismatches:
                print(f"  {mf}: {h1[:12]} != {h2[:12]}")
            return False

        print(f"[PASS] Determinism verified! {len(files1)} files matched byte-for-byte.")
        return True
