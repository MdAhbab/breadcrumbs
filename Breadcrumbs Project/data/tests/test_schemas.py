"""
Acceptance Test 3: Every document validates against its schema; anomaly row index is in range.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from data.config import CorpusConfig
from data.generator import StreamingCorpusGenerator
from data.io_utils import read_jsonl_gz
from data.schemas import validate_row_schema


def test_every_document_schema_and_anomaly_row_in_range():
    """Verify all 5 record types validate against row schemas and anomaly_row < len(rows)."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = CorpusConfig(seed=42, scale="small", total_docs=800, output_dir=tmp)
        gen = StreamingCorpusGenerator(cfg)
        gen.generate_corpus()

        shards = list(Path(tmp).glob("documents/**/*.jsonl.gz"))
        assert len(shards) > 0, "No shards found"

        seen_types = set()
        for shard in shards:
            docs = read_jsonl_gz(shard)
            for d in docs:
                rec_type = d["record_type"]
                seen_types.add(rec_type)
                rows = d["rows"]
                assert len(rows) > 0, f"Empty rows in document {d['doc_id']}"

                # If labelled anomalous with an anomaly_row, index must be strictly valid
                if d["label"] == 1 and d.get("anomaly_row") is not None:
                    row_idx = d["anomaly_row"]
                    assert 0 <= row_idx < len(rows), (
                        f"anomaly_row {row_idx} out of range [0, {len(rows)}) in {d['doc_id']}"
                    )

                # Validate every row against schema
                for r in rows:
                    ok, msg = validate_row_schema(rec_type, r)
                    assert ok, f"Row validation failure in {d['doc_id']} ({rec_type}): {msg}"

        # Ensure all 5 record types were generated and tested
        expected_types = {
            "payroll_register",
            "safety_inspection",
            "chemical_inventory",
            "machine_maintenance",
            "production_output",
        }
        assert seen_types == expected_types, f"Missing record types: {expected_types - seen_types}"
