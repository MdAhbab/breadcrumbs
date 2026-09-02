"""
Acceptance Test 7: Trace events resolve to existing documents; withheld sets are consistent.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from data.config import CorpusConfig
from data.generator import StreamingCorpusGenerator


def test_adversary_trace_consistency_and_withholding_resolution():
    """Verify trace references resolve to ground truth and withholding invariants hold."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = CorpusConfig(seed=7, scale="small", total_docs=1000, attack_rate=0.15, output_dir=tmp)
        gen = StreamingCorpusGenerator(cfg)
        gen.generate_corpus()

        tmp_path = Path(tmp)
        with open(tmp_path / "ground_truth.json") as fh:
            ground_truth = json.load(fh)

        with open(tmp_path / "adversary_trace.json") as fh:
            trace = json.load(fh)

        gt_docs = ground_truth["documents"]
        events = trace["events"]
        assert len(events) > 0, "No adversary events generated"

        for event in events:
            # Check target document existence if specified
            target_id = event.get("target_doc_id")
            if target_id is not None:
                # Strip -v2 if looking up original
                clean_target = target_id.replace("-v2", "")
                assert (clean_target in gt_docs) or (target_id in gt_docs), (
                    f"Trace event {event['event_id']} target {target_id} not found in ground truth"
                )

            # Check withholding invariants (§7.2)
            if event["attack_type"] == "withholding":
                params = event["parameters"]
                withheld_ids = params["withheld_doc_ids"]
                disclosed_ids = params["disclosed_doc_ids"]

                # Disclosed and withheld must be mutually disjoint
                assert set(disclosed_ids).isdisjoint(set(withheld_ids)), (
                    f"Disclosed and withheld overlap in event {event['event_id']}"
                )

                # Total count must equal sum
                assert params["total_produced"] == len(disclosed_ids) + len(withheld_ids)

                # Every withheld doc must exist in ground truth with is_withheld=True
                for wid in withheld_ids:
                    assert wid in gt_docs, f"Withheld doc {wid} missing from ground truth"
                    assert gt_docs[wid]["is_withheld"] is True, (
                        f"Doc {wid} in withholding event not marked is_withheld in ground truth"
                    )
