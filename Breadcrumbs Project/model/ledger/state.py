"""
World state: the current value of every key, plus its version.

The blockchain is the history; the world state is the answer to "what is true
now". Keeping both is not redundancy. Replaying 14,000 blocks to answer one
query would be absurd, and throwing the blocks away would leave nothing to audit.

Versions are what make concurrent commits safe. Every write bumps the key's
version. A transaction that read version 3 of a key and arrives after someone
else wrote version 4 is rejected at validation, not silently applied on top.

SQLite backs this because it is in the standard library, gives real durability,
and gives the backend something to query directly.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS world_state (
    channel  TEXT NOT NULL,
    key      TEXT NOT NULL,
    value    TEXT,
    version  INTEGER NOT NULL,
    PRIMARY KEY (channel, key)
);
CREATE TABLE IF NOT EXISTS blocks (
    channel  TEXT NOT NULL,
    number   INTEGER NOT NULL,
    hash     TEXT NOT NULL,
    body     TEXT NOT NULL,
    PRIMARY KEY (channel, number)
);
CREATE INDEX IF NOT EXISTS idx_blocks_hash ON blocks(hash);
"""


class WorldState:
    """Versioned key-value store, one namespace per channel."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # A web server answers requests on a pool of threads, and sqlite3
        # refuses by default to let a connection cross one. Sharing a single
        # connection guarded by a lock is the right trade here: the ledger is
        # append-only and low-throughput, and serialising access also gives the
        # commit path the mutual exclusion it needs anyway — two blocks must
        # never interleave their writes.
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self.conn.executescript(_SCHEMA)
            self.conn.commit()

    # -- reads ------------------------------------------------------------
    def get(self, channel: str, key: str) -> tuple[Any, int]:
        """Returns (value, version). A missing key is (None, 0), not an error."""
        with self._lock:
            row = self.conn.execute(
                "SELECT value, version FROM world_state WHERE channel=? AND key=?",
                (channel, key),
            ).fetchone()
        if row is None:
            return None, 0
        value = json.loads(row["value"]) if row["value"] is not None else None
        return value, row["version"]

    def version(self, channel: str, key: str) -> int:
        return self.get(channel, key)[1]

    def range(self, channel: str, prefix: str) -> Iterator[tuple[str, Any]]:
        """Every key under a prefix, in key order. The chaincode 'query' path."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT key, value FROM world_state "
                "WHERE channel=? AND key LIKE ? AND value IS NOT NULL ORDER BY key",
                (channel, prefix + "%"),
            ).fetchall()
        for row in rows:
            yield row["key"], json.loads(row["value"])

    # -- writes -----------------------------------------------------------
    def apply(self, channel: str, key: str, value: Any) -> int:
        """Set a key and bump its version. Returns the new version."""
        _, current = self.get(channel, key)
        new_version = current + 1
        encoded = None if value is None else json.dumps(value, sort_keys=True)
        with self._lock:
            self.conn.execute(
                "INSERT INTO world_state(channel,key,value,version) VALUES(?,?,?,?) "
                "ON CONFLICT(channel,key) DO UPDATE SET value=excluded.value, "
                "version=excluded.version",
                (channel, key, encoded, new_version),
            )
        return new_version

    def commit(self) -> None:
        with self._lock:
            self.conn.commit()

    # -- block storage ----------------------------------------------------
    def store_block(self, channel: str, number: int, block_hash: str, body: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO blocks(channel,number,hash,body) VALUES(?,?,?,?)",
                (channel, number, block_hash, json.dumps(body, sort_keys=True)),
            )

    def load_block(self, channel: str, number: int) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT body FROM blocks WHERE channel=? AND number=?", (channel, number)
            ).fetchone()
        return json.loads(row["body"]) if row else None

    def height(self, channel: str) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT MAX(number) AS n FROM blocks WHERE channel=?", (channel,)
            ).fetchone()
        return -1 if row["n"] is None else row["n"]

    def close(self) -> None:
        with self._lock:
            self.conn.commit()
            self.conn.close()
