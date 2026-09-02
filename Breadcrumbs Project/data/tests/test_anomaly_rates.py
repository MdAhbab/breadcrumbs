"""
Acceptance Test 4: Anomaly rate per site and per wave is within configuration tolerance.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from data.config import CorpusConfig
from data.generator import StreamingCorpusGenerator


def test_anomaly_rates_per_site_and_wave_within_tolerance():
    """Verify that overall, per-site, and per-wave anomaly rates match the 4% target."""
    target_rate = 0.04
    with tempfile.TemporaryDirectory() as tmp:
        # Scale to 2,000 docs for statistical stability
        cfg = CorpusConfig(seed=123, scale="small", total_docs=2000, anomaly_rate=target_rate, output_dir=tmp)
        gen = StreamingCorpusGenerator(cfg)
        gen.generate_corpus()

        with open(Path(tmp) / "stats.json") as fh:
            stats = json.load(fh)

        overall_rate = stats["overall_anomaly_rate"]
        # Overall rate within +- 1.5% absolute tolerance
        assert abs(overall_rate - target_rate) < 0.015, (
            f"Overall rate {overall_rate} deviated from target {target_rate}"
        )

        # Check wave rates
        for wave_id, w_data in stats["by_wave"].items():
            w_total = w_data["total"]
            w_anom = w_data["anomalous"]
            if w_total > 50:
                w_rate = w_anom / w_total
                assert abs(w_rate - target_rate) < 0.025, (
                    f"Wave {wave_id} rate {w_rate:.4f} deviated from target {target_rate}"
                )

        # Check site rates
        for site_key, s_data in stats["by_site"].items():
            s_total = s_data["total"]
            s_anom = s_data["anomalous"]
            if s_total > 50:
                s_rate = s_anom / s_total
                assert abs(s_rate - target_rate) < 0.03, (
                    f"Site {site_key} rate {s_rate:.4f} deviated from target {target_rate}"
                )
