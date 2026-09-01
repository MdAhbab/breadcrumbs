"""
Who must counter-sign a record, and how they are chosen.

THE PROBLEM. The report concedes it in §11 and it is the most honest sentence in
the document: "a signed record of a false statement is still a correct record of
a lie." A ledger makes a record unchangeable. It does nothing about whether the
record was true when it was written. Every provenance system ever built has this
hole and most of them do not admit it.

THE NARROWING. Require a second organisation to counter-sign at capture, and
unilateral falsification stops being possible. It does not become impossible —
two organisations can still collude — but it becomes a conspiracy rather than a
decision, it is recorded, it is attributable, and both parties lose reputation
when it is found. That is a real change in the cost of lying, and it is the most
that any system in this class can honestly claim.

WHY THE WITNESS IS ASSIGNED AND NOT CHOSEN. A factory that picks its own
counter-signatory has bought an alibi, not a check. So the assignment is
computed from a seed no single member controls, mixed with the record's own
identifier. Both halves are needed: without the record id every record in a
period would draw the same witness; without the shared seed the factory could
grind record identifiers until a friendly witness came up.

WHY THE SEED IS COMMIT-REVEAL. If the seed were simply published, whoever
published it last could try values until the assignment suited them. Each member
commits to a hash first and reveals afterwards, so a member choosing its share
does not yet know anybody else's, and the result is unpredictable to all of them
unless every single one colludes.

WHAT THE WITNESS IS ACTUALLY SAYING. `check_code` is not decoration. A witness
that signs `physical_presence` is claiming somebody stood in the room; one that
signs `sample_row_recompute` is claiming it recomputed rows against a source
system. These are different claims with different evidentiary weight, and a
witness that signs the strongest one for a record that turns out to be false has
made a specific, attributable, slashable assertion rather than a vague gesture.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..ledger.crypto import canonical

# Record types where a counter-signature is always required. These are the ones
# a compliance dispute actually turns on, and the ones worth the cost.
ALWAYS_WITNESSED = {"payroll_register", "safety_inspection"}

# What a witness can claim to have done, in increasing order of weight.
CHECK_CODES = {
    "format_only",            # the document is well formed and internally consistent
    "sample_row_recompute",   # a sample of rows was recomputed against a source system
    "source_system_readback", # the totals were read back out of the originating system
    "physical_presence",      # somebody from the witnessing organisation was on site
}

WITNESS_QUORUM = 1  # counter-signatories required per witnessed record


def seed_from_shares(shares: dict[str, str]) -> str:
    """
    Combine revealed shares into one seed.

    Sorted by member so that every peer derives the same value regardless of the
    order the reveals arrived in — the usual determinism rule, and the usual way
    it gets broken.
    """
    d = hashlib.sha256()
    d.update(b"breadcrumbs:witnessseed:v1")
    for member in sorted(shares):
        d.update(member.encode("utf-8"))
        d.update(bytes.fromhex(shares[member]))
    return d.hexdigest()


def share_commitment(share_hex: str) -> str:
    """The digest a member publishes before revealing its share."""
    d = hashlib.sha256()
    d.update(b"breadcrumbs:witnessshare:v1")
    d.update(bytes.fromhex(share_hex))
    return d.hexdigest()


def is_witnessed(seed: str, record_id: str, record_type: str, sample_percent: int) -> bool:
    """
    Does this record need a counter-signature?

    Witnessing everything is the right answer for a paper and the wrong one for a
    factory producing four hundred documents a month. High-stakes types are
    always witnessed; the rest are sampled, at a rate the consortium sets. The
    sample is drawn from the shared seed so a factory cannot tell in advance
    which of its routine records will be checked — which is the property that
    makes a partial sample deter anything at all.
    """
    if record_type in ALWAYS_WITNESSED:
        return True
    if sample_percent <= 0:
        return False
    if sample_percent >= 100:
        return True
    draw = int(
        hashlib.sha256(b"breadcrumbs:witnesssample:v1" + canonical([seed, record_id])).hexdigest(),
        16,
    )
    return draw % 100 < sample_percent


def assign_witnesses(seed: str, record_id: str, pool: list[str], quorum: int) -> list[str]:
    """
    Pick the counter-signatories for one record, deterministically.

    Every endorsing peer runs this and must produce the same answer, so there is
    no randomness in it: the draw is a hash of the seed and the record id, and
    the pool is sorted before use. Selection is without replacement, because a
    quorum of two that drew the same organisation twice would be a quorum of one
    wearing a hat.
    """
    candidates = sorted(pool)
    if quorum > len(candidates):
        raise ValueError(
            f"a quorum of {quorum} cannot be drawn from {len(candidates)} eligible organisations"
        )
    chosen: list[str] = []
    attempt = 0
    while len(chosen) < quorum:
        draw = int(
            hashlib.sha256(
                b"breadcrumbs:witnessassign:v1" + canonical([seed, record_id, attempt])
            ).hexdigest(),
            16,
        )
        candidate = candidates[draw % len(candidates)]
        if candidate not in chosen:
            chosen.append(candidate)
        attempt += 1
        if attempt > 1000:  # unreachable with a non-empty pool; a guard, not a policy
            raise ValueError("could not draw a witness quorum")
    return sorted(chosen)


def attestation_payload(record: dict[str, Any], check_code: str, timestamp: str) -> dict[str, Any]:
    """
    Exactly what a witness signs.

    It binds the record identifier, the Merkle root and the bucket. Binding the
    root is what stops an attestation being lifted from one document and attached
    to another with the same name — the signature would still verify, and the
    claim would be about content the witness never saw.
    """
    return {
        "record_id": record["record_id"],
        "merkle_root": record["merkle_root"],
        "bucket": record["bucket"],
        "owner_msp": record["owner_msp"],
        "check_code": check_code,
        "attested_at": timestamp,
    }
