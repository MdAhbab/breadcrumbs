"""
Deterministic I/O utilities, canonical JSON serialization, and streaming writers (§8, §9).

Ensures:
- Canonical JSON encoding with sorted keys and tight separators.
- Deterministic gzip compression (fixed mtime=0) to guarantee byte-identical outputs across runs.
- SHA-256 calculation for file and manifest integrity.
- Streaming chunk writers with lazy Parquet export support.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def canonical_json_dumps(obj: Any) -> str:
    """Serialize object to strictly canonical JSON string."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def calculate_sha256(filepath: Path | str) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while chunk := fh.read(65536):
            h.update(chunk)
    return h.hexdigest()


def calculate_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def write_canonical_json(filepath: Path | str, obj: Any) -> str:
    """Write object to canonical JSON file and return its SHA-256 hash."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = canonical_json_dumps(obj).encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(serialized)
    return calculate_bytes_sha256(serialized)


def write_jsonl_gz(filepath: Path | str, records: Iterable[dict[str, Any]]) -> str:
    """
    Write iterable of dicts to a deterministic .jsonl.gz file (mtime=0).
    Returns the SHA-256 hash of the generated file.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Use io.BytesIO buffer with fixed mtime=0 for deterministic gzip output
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0.0) as gz:
        for record in records:
            line = canonical_json_dumps(record) + "\n"
            gz.write(line.encode("utf-8"))

    compressed_bytes = buf.getvalue()
    with open(path, "wb") as fh:
        fh.write(compressed_bytes)

    return calculate_bytes_sha256(compressed_bytes)


def read_jsonl_gz(filepath: Path | str) -> list[dict[str, Any]]:
    """Read records from a .jsonl.gz file."""
    records = []
    with gzip.open(filepath, "rt", encoding="utf-8") as gz:
        for line in gz:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_parquet(filepath: Path | str, records: list[dict[str, Any]]) -> None:
    """
    Optional lazy parquet writer using pandas and pyarrow.
    Imports dependencies lazily to avoid forcing pyarrow when not requested.
    """
    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("Parquet output requires pandas and pyarrow to be installed.") from exc

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)
    table = pa.Table.from_pandas(df)
    pq.write_table(table, str(path))
