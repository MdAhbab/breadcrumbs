"""
Epoch digests, gossip between members, and detecting a forked history.

THE GAP THIS CLOSES. The security audit records it as §3.5: everything runs in one
process against one SQLite file, so an attacker with write access to both could
rewrite history *consistently* — every hash link recomputed, every block
re-signed, nothing internally contradictory. Hash chains detect tampering by
someone who cannot rewrite the whole chain. They detect nothing at all from
someone who can.

The defence is not more cryptography. It is that a rewritten history has to be
shown to somebody, and everybody who was shown the old one still remembers it.
Each member signs a short digest of every epoch it observes and hands it to the
others. Rewriting history now means producing a chain that contradicts digests
already sitting in other organisations' files, signed by their own keys. The
attacker cannot recall those, and cannot forge them without those organisations'
private keys.

WHAT THIS DOES AND DOES NOT PROVE. It proves *non-equivocation*: two members
holding different digests for the same epoch is conclusive evidence that
somebody served two different histories, and the epoch it happened at is named
exactly. It does not prove which of the two is genuine — that needs a third
member, or an external anchor, and the arithmetic is ordinary quorum counting
rather than anything clever. A consortium where every member is dishonest gets
no help from this or from anything else.

WHY IT IS CHEAP. A digest is about a hundred bytes. Publishing one per epoch to
six organisations is less traffic than a single document commitment, so there is
no reason for a deployment to skip it, and a deployment that skipped it would be
relying on the honesty of whoever runs the storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .crypto import TAG_SEAL, canonical, h, sign, verify
from .identity import MSP, Identity


def epoch_digest(
    channel: str,
    epoch: int,
    accumulator_hex: str,
    block_number: int,
    block_hash: str,
    parameters_hash: str,
) -> dict[str, Any]:
    """
    The short statement a member publishes about what it saw.

    Both the accumulator value and the block hash are in it, and both are needed.
    The accumulator commits to the record set; the block hash commits to the order
    events happened in. A history rewritten to change either one produces a
    different digest, and a history rewritten to change neither has not changed
    anything that matters.
    """
    body = {
        "channel": channel,
        "epoch": epoch,
        "accumulator_hex": accumulator_hex,
        "block_number": block_number,
        "block_hash": block_hash,
        "parameters_hash": parameters_hash,
    }
    return {**body, "digest": h(TAG_SEAL, canonical(body))}


@dataclass(frozen=True)
class SignedDigest:
    """One organisation's signed assertion about one epoch."""

    msp_id: str
    identity_id: str
    certificate_pem: str
    digest: dict[str, Any]
    signature: str
    observed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "msp_id": self.msp_id,
            "identity_id": self.identity_id,
            "certificate_pem": self.certificate_pem,
            "digest": self.digest,
            "signature": self.signature,
            "observed_at": self.observed_at,
        }


def attest(identity: Identity, digest: dict[str, Any], timestamp: str) -> SignedDigest:
    """Sign a digest as an organisation. This is the whole publishing protocol."""
    return SignedDigest(
        msp_id=identity.msp_id,
        identity_id=identity.id,
        certificate_pem=identity.certificate_pem(),
        digest=digest,
        signature=sign(identity.private_key, digest),
        observed_at=timestamp,
    )


@dataclass
class Divergence:
    """Two members, one epoch, two irreconcilable stories."""

    channel: str
    epoch: int
    views: dict[str, list[str]]  # digest -> the organisations asserting it

    @property
    def parties(self) -> list[str]:
        return sorted({m for members in self.views.values() for m in members})

    def describe(self) -> str:
        lines = [
            f"FORK DETECTED on {self.channel} at epoch {self.epoch}: "
            f"{len(self.views)} irreconcilable views."
        ]
        for digest, members in sorted(self.views.items()):
            lines.append(f"  {digest[:16]}… asserted by {', '.join(sorted(members))}")
        lines.append(
            "  Neither view is proved genuine by this alone. A majority of "
            "independent members, or an external anchor, decides which history "
            "the consortium keeps."
        )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "epoch": self.epoch,
            "views": {d: sorted(m) for d, m in self.views.items()},
            "parties": self.parties,
        }


@dataclass
class DigestRegistry:
    """
    What one organisation has been told by the others, and what it makes of it.

    Every member runs one. It is deliberately dumb: it stores signed assertions
    and compares them. There is no consensus protocol here and there should not
    be — the value is precisely that this is simple enough that a member can
    reimplement it in an afternoon and not have to trust anybody's client.
    """

    msp: MSP
    observations: dict[tuple[str, int], dict[str, SignedDigest]] = field(default_factory=dict)
    rejected: list[str] = field(default_factory=list)

    def observe(self, signed: SignedDigest) -> tuple[bool, str]:
        """
        Record another organisation's assertion, after checking it is really theirs.

        The certificate is resolved through the MSP before the signature is
        checked, for the reason that governs every signature check in this
        codebase: a signature proves somebody holds a private key and nothing
        about who they are. Skipping it here would let an attacker manufacture
        agreement from organisations that never said anything.
        """
        public_key, reason = self.msp.public_key_for(signed.msp_id, signed.certificate_pem)
        if public_key is None:
            self.rejected.append(f"{signed.msp_id}: {reason}")
            return False, reason
        if not verify(public_key, signed.digest, signed.signature):
            self.rejected.append(f"{signed.msp_id}: signature does not verify")
            return False, "signature does not verify"

        recomputed = epoch_digest(
            signed.digest["channel"],
            signed.digest["epoch"],
            signed.digest["accumulator_hex"],
            signed.digest["block_number"],
            signed.digest["block_hash"],
            signed.digest["parameters_hash"],
        )["digest"]
        if recomputed != signed.digest["digest"]:
            self.rejected.append(f"{signed.msp_id}: digest does not match its own contents")
            return False, "digest does not match its own contents"

        key = (signed.digest["channel"], int(signed.digest["epoch"]))
        self.observations.setdefault(key, {})[signed.msp_id] = signed
        return True, ""

    def fork_at(self, channel: str, epoch: int) -> Divergence | None:
        """Is there a disagreement about this epoch?"""
        seen = self.observations.get((channel, epoch), {})
        views: dict[str, list[str]] = {}
        for msp_id, signed in seen.items():
            views.setdefault(signed.digest["digest"], []).append(msp_id)
        if len(views) <= 1:
            return None
        return Divergence(channel=channel, epoch=epoch, views=views)

    def forks(self, channel: str | None = None) -> list[Divergence]:
        """Every disagreement on record, earliest epoch first."""
        out = []
        for ch, epoch in sorted(self.observations):
            if channel is not None and ch != channel:
                continue
            divergence = self.fork_at(ch, epoch)
            if divergence is not None:
                out.append(divergence)
        return out

    def majority(self, channel: str, epoch: int) -> tuple[str | None, int, int]:
        """
        Which view most members assert. Returns (digest, supporting, total).

        A bare majority is reported, not enforced. Deciding what to do about a
        fork is a governance question — it may mean expelling a member — and a
        library that silently picked a winner would be making that decision on
        the consortium's behalf.
        """
        seen = self.observations.get((channel, epoch), {})
        if not seen:
            return None, 0, 0
        counts: dict[str, int] = {}
        for signed in seen.values():
            counts[signed.digest["digest"]] = counts.get(signed.digest["digest"], 0) + 1
        best = max(counts, key=lambda d: (counts[d], d))
        return best, counts[best], len(seen)
