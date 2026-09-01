"""
Merkle trees and single-line selective disclosure.

This is Plane A of the report, and the thing a buyer actually sees. A payroll
register with 1,847 rows is hashed row by row into a tree. Only the root goes on
the ledger. Later, to prove that one specific row is genuine, the factory reveals
that row, its salt, and about eleven sibling hashes — enough to recompute the
root, and nothing more. The other 1,846 rows are never transmitted and cannot be
recovered from the proof.

Two defences are built in, and both are here because their absence is a known
class of bug rather than a hypothetical:

  Salting. Wage rows have low entropy. Without a per-row salt, an auditor
  holding the proof for one row could brute-force a neighbouring row's value by
  hashing guesses. Each leaf carries its own 128-bit salt, released only with
  that row's proof.

  Domain separation. Leaves and internal nodes are hashed with different tags,
  so an internal node's hash can never be presented as a leaf. Without it, a
  forged proof can pass off a subtree as a record.

Odd nodes are promoted, not duplicated. Duplicating the last hash is the
CVE-2012-2459 bug: two different row lists then produce the same root.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ledger.crypto import TAG_PUBLIC_LEAF, canonical, h, leaf_hash, new_salt, node_hash


@dataclass
class ProofStep:
    """One rung of the ladder from a leaf to the root."""

    sibling: str
    position: str  # "left" or "right": which side the sibling sits on

    def to_dict(self) -> dict[str, str]:
        return {"sibling": self.sibling, "position": self.position}


@dataclass
class Disclosure:
    """
    Everything a verifier needs, and nothing else.

    Note what is absent: any other row, the number of rows, or any aggregate.
    The index is included because the verifier needs to know which side to hash
    on at each level, and it leaks only a position.
    """

    record_id: str
    field_name: str
    value: Any
    salt: str
    index: int
    path: list[ProofStep]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "field_name": self.field_name,
            "value": self.value,
            "salt": self.salt,
            "index": self.index,
            "path": [s.to_dict() for s in self.path],
        }


class MerkleTree:
    """A tree over one document's rows."""

    def __init__(self, rows: list[Any], salts: list[str] | None = None):
        if not rows:
            raise ValueError("cannot build a Merkle tree over zero rows")
        self.rows = rows
        self.salts = salts or [new_salt() for _ in rows]
        if len(self.salts) != len(rows):
            raise ValueError("need exactly one salt per row")
        self.leaves = [leaf_hash(r, s) for r, s in zip(rows, self.salts, strict=True)]
        self.levels: list[list[str]] = [list(self.leaves)]
        self._build()

    def _build(self) -> None:
        level = self.levels[0]
        while len(level) > 1:
            nxt: list[str] = []
            for i in range(0, len(level) - 1, 2):
                nxt.append(node_hash(level[i], level[i + 1]))
            if len(level) % 2 == 1:
                nxt.append(level[-1])  # promote, never duplicate
            self.levels.append(nxt)
            level = nxt

    @property
    def root(self) -> str:
        return self.levels[-1][0]

    @property
    def size(self) -> int:
        return len(self.rows)

    def prove(self, index: int, record_id: str, field_name: str) -> Disclosure:
        """Build the proof for one row."""
        if not 0 <= index < len(self.rows):
            raise IndexError(f"row {index} is outside this document's {len(self.rows)} rows")

        path: list[ProofStep] = []
        idx = index
        for level in self.levels[:-1]:
            if idx % 2 == 0:
                sibling_idx = idx + 1
                position = "right"
            else:
                sibling_idx = idx - 1
                position = "left"
            if sibling_idx < len(level):
                path.append(ProofStep(level[sibling_idx], position))
            # When the sibling does not exist this node was promoted unchanged,
            # so there is nothing to combine with at this level.
            idx //= 2

        return Disclosure(
            record_id=record_id,
            field_name=field_name,
            value=self.rows[index],
            salt=self.salts[index],
            index=index,
            path=path,
        )


def verify_disclosure(disclosure: Disclosure, committed_root: str) -> tuple[bool, str, list[str]]:
    """
    Recompute the root from a disclosure alone.

    This runs on the *verifier's* side and needs nothing from the factory beyond
    the disclosure itself and the root already on the ledger. Returns
    (ok, computed_root, the intermediate hashes) so the UI can show the ladder.
    """
    current = leaf_hash(disclosure.value, disclosure.salt)
    trace = [current]
    for step in disclosure.path:
        if step.position == "right":
            current = node_hash(current, step.sibling)
        else:
            current = node_hash(step.sibling, current)
        trace.append(current)
    return current == committed_root, current, trace


def public_root(items: list[str]) -> str:
    """
    A Merkle root over a list of public values, with no salts.

    Salts exist in the tree above because wage rows have low entropy and a
    verifier holding one proof could otherwise brute-force its neighbours. That
    reasoning does not apply to a list of record identifiers: both sides already
    hold them, they are not secret, and a salt would make the root impossible for
    a verifier to recompute independently — which is the entire job here.

    This is what a period seal commits to. A factory that later hands over a
    shortened list produces a different root, and the seal on the ledger refuses
    it. That is how "nothing is missing" becomes checkable rather than asserted.

    The list is sorted before hashing so that two parties holding the same set in
    different orders derive the same root.
    """
    if not items:
        return h(TAG_PUBLIC_LEAF, b"")
    level = [h(TAG_PUBLIC_LEAF, canonical(item)) for item in sorted(items)]
    while len(level) > 1:
        nxt: list[str] = []
        for i in range(0, len(level) - 1, 2):
            nxt.append(node_hash(level[i], level[i + 1]))
        if len(level) % 2 == 1:
            nxt.append(level[-1])  # promoted, never duplicated: CVE-2012-2459
        level = nxt
    return level[0]
