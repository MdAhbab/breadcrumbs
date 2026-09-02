"""
Acceptance Test 9: Streaming generator stays under a strict memory ceiling.
"""

from __future__ import annotations

import tempfile
import tracemalloc

from data.config import CorpusConfig
from data.generator import StreamingCorpusGenerator


def test_streaming_generator_stays_under_memory_ceiling():
    """Verify that streaming generation across multiple shards stays under 100 MB peak RAM."""
    tracemalloc.start()
    tracemalloc.reset_peak()

    with tempfile.TemporaryDirectory() as tmp:
        # Generate 5,000 documents across 36 periods and 6 sites
        cfg = CorpusConfig(seed=7, scale="small", total_docs=5000, output_dir=tmp)
        gen = StreamingCorpusGenerator(cfg)
        gen.generate_corpus()

        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_mem / (1024 * 1024)
        # Memory ceiling: peak allocated memory during 5k doc streaming must stay under 100 MB
        assert peak_mb < 100.0, f"Peak memory {peak_mb:.2f} MB exceeded ceiling of 100 MB"
