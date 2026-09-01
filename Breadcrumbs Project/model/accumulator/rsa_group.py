"""
The group everything else in this package lives in.

Breadcrumbs needs a *group of unknown order*: a set with multiplication where
nobody can work out how many elements it has. That single property is what makes
four separate mechanisms possible, and it is the reason RSA is here rather than
a faster signature scheme. In such a group you cannot compute an arbitrary root,
which is what stops an attacker inventing a membership witness; and you cannot
shortcut repeated squaring, which is what makes a delay function honest.

The group is (Z/NZ)* / {+1,-1} — the integers modulo N, with x and N-x treated as
the same element. Quotienting by the sign removes the one element of small order
that is easy to find, which would otherwise let an attacker take square roots of
some elements for free. Every value that leaves this module is normalised to the
smaller of the two representatives, so equality is unambiguous and two peers
serialising the same element produce identical bytes.

WHO KNOWS THE FACTORISATION, AND WHY IT IS SURVIVABLE
Whoever knows p and q knows the group's order and can forge any membership
witness they like. That is the standard objection to RSA accumulators and it is
a real one. Breadcrumbs answers it structurally rather than by insisting the
trapdoor is safe:

  the accumulator is never the authority.

A membership witness is accepted only when it agrees with the Merkle proof and
the hash-chained block that already commit the same record. The accumulator's
job is to make verification cheap and to answer questions Merkle trees cannot
answer at all — "this record was never committed", "nothing is missing from this
period". Someone holding the trapdoor can produce a witness for a record that
was never committed; they cannot produce the block, the endorsements or the
Merkle path that the verifier also checks. So the attack degrades to a failed
verification rather than a forged history. `model/tests/test_attacks_insider.py`
hands an attacker the factorisation and demonstrates exactly that.

This is worth stating plainly in the report rather than hoping nobody asks,
because the alternative designs all cost something. Distributed modulus
generation in the style of Boneh-Franklin removes the dealer but is a research
protocol, not a fortnight's work. Class groups of imaginary quadratic order have
no trapdoor at all, but they are slower and they stop being RSA.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any

from ..ledger.crypto import canonical, h

TAG_GROUP = b"breadcrumbs:rsagroup:v1"
TAG_CEREMONY = b"breadcrumbs:ceremony:v1"

# Bits for a locally generated modulus. 3072 is the NIST-recommended size for
# security through 2030; see `model/ledger/suites.py` for what happens after that.
DEFAULT_MODULUS_BITS = 3072


class GroupError(Exception):
    """Raised when an element or a parameter is not usable in this group."""


def _hash_int(*parts: bytes) -> int:
    """A 512-bit integer derived from the parts, for deriving group elements."""
    a = hashlib.sha512()
    for p in parts:
        a.update(len(p).to_bytes(8, "big"))
        a.update(p)
    return int.from_bytes(a.digest(), "big")


@dataclass(frozen=True)
class RSAGroup:
    """
    An RSA modulus, a generator, and the provenance of both.

    `provenance` is not decoration. A verifier needs to know where N came from to
    judge what the accumulator is worth, and burying that in a deployment
    document means it gets lost. It travels with the group.
    """

    modulus: int
    generator: int
    provenance: str
    suite: str = "rsa-3072-sha256-v1"

    # -- construction -----------------------------------------------------
    @staticmethod
    def _derive_generator(modulus: int) -> int:
        """
        A generator nobody chose.

        Squaring puts the result in the subgroup of quadratic residues, which has
        no element of order 2 and is where accumulator security proofs live.
        Deriving it from a hash of the modulus rather than picking one means no
        participant can claim a special relationship with it.
        """
        base = _hash_int(TAG_GROUP, modulus.to_bytes((modulus.bit_length() + 7) // 8, "big"))
        g = pow(base % modulus, 2, modulus)
        g = min(g, modulus - g)
        if g <= 1:
            raise GroupError("degenerate generator; the modulus is not usable")
        return g

    @classmethod
    def from_public_modulus(cls, modulus: int, provenance: str) -> RSAGroup:
        """
        Use a modulus whose factorisation is believed lost — an RSA Factoring
        Challenge number, or one derived from a public random beacon.

        `provenance` must say which, in words a reader can check. Passing
        "trust me" here is not an error the code can catch, so it is one the
        report has to answer for.
        """
        if modulus.bit_length() < 2048:
            raise GroupError(f"modulus is {modulus.bit_length()} bits; 2048 is the floor")
        if modulus % 2 == 0:
            raise GroupError("modulus is even")
        return cls(modulus=modulus, generator=cls._derive_generator(modulus), provenance=provenance)

    @classmethod
    def generate_untrusted(cls, bits: int = DEFAULT_MODULUS_BITS) -> tuple[RSAGroup, int, int]:
        """
        Generate a modulus AND return its factors. **Never use in production.**

        This exists for two legitimate reasons. Tests need a small modulus so the
        suite runs in seconds. And the attack demonstration needs the trapdoor:
        the only way to show that holding p and q does not let you rewrite
        history is to hold p and q and try.

        The factors are returned rather than discarded precisely so that no
        caller can pretend this is a safe construction.
        """
        p = _random_prime(bits // 2)
        q = _random_prime(bits - bits // 2)
        while q == p:
            q = _random_prime(bits - bits // 2)
        n = p * q
        group = cls(
            modulus=n,
            generator=cls._derive_generator(n),
            provenance=f"locally generated {bits}-bit modulus; FACTORS KNOWN, testing only",
        )
        return group, p, q

    # -- group operations -------------------------------------------------
    def normalise(self, x: int) -> int:
        """Fold x and N-x onto one representative. Every element leaves here normalised."""
        x %= self.modulus
        return min(x, self.modulus - x)

    def contains(self, x: int) -> bool:
        """
        Membership: a positive residue that is invertible modulo N.

        The identity, 1, is a member and must be accepted. It looks degenerate
        and it is tempting to exclude, but a proof of exponentiation with a
        quotient of zero legitimately produces it, and rejecting it here breaks
        every short-exponent proof. Elements sharing a factor with N are refused:
        finding one means having factored the modulus, and there is no honest way
        to be holding it.
        """
        if not 0 < x < self.modulus:
            return False
        return _gcd(x, self.modulus) == 1

    def mul(self, a: int, b: int) -> int:
        return self.normalise(a * b)

    def exp(self, base: int, exponent: int) -> int:
        """
        base^exponent, with negative exponents handled by inversion.

        Non-membership witnesses produce a negative Bezout coefficient about half
        the time, so this is a normal path rather than an edge case.
        """
        if exponent >= 0:
            return self.normalise(pow(base, exponent, self.modulus))
        inverse = pow(base, -1, self.modulus)
        return self.normalise(pow(inverse, -exponent, self.modulus))

    def element_from(self, payload: Any) -> int:
        """Deterministically map an object to a group element, for VDF inputs."""
        base = _hash_int(TAG_GROUP, canonical(payload))
        return self.normalise(pow(base % self.modulus, 2, self.modulus))

    # -- serialisation ----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """
        Canonical form. Integers go out as hex strings.

        Not as JSON numbers: a 3072-bit integer is silently mangled by every
        JSON parser that maps numbers to doubles, and the frontend has one.
        """
        return {
            "suite": self.suite,
            "modulus_hex": format(self.modulus, "x"),
            "modulus_bits": self.modulus.bit_length(),
            "generator_hex": format(self.generator, "x"),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RSAGroup:
        return cls(
            modulus=int(d["modulus_hex"], 16),
            generator=int(d["generator_hex"], 16),
            provenance=d["provenance"],
            suite=d.get("suite", "rsa-3072-sha256-v1"),
        )

    @property
    def parameters_hash(self) -> str:
        """One digest binding the modulus, generator and suite. Goes on the ledger."""
        return h(TAG_GROUP, canonical(self.to_dict()))


# --------------------------------------------------------------------------
# The ceremony
# --------------------------------------------------------------------------
@dataclass
class CeremonyTranscript:
    """
    The public record of how the modulus was produced.

    Written to the ledger at consortium formation. It does not make a
    trusted-dealer ceremony into a distributed one — nothing can, short of
    running the real protocol — but it makes the trust assumption *named*,
    *timestamped* and *attributable*, so a member joining in year three can read
    who was in the room and decide what the accumulator is worth to them.
    """

    modulus_bits: int
    dealer: str
    contributors: list[str]
    contribution_hashes: dict[str, str]
    attestations: dict[str, str]
    parameters_hash: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "modulus_bits": self.modulus_bits,
            "dealer": self.dealer,
            "contributors": sorted(self.contributors),
            "contribution_hashes": dict(sorted(self.contribution_hashes.items())),
            "attestations": dict(sorted(self.attestations.items())),
            "parameters_hash": self.parameters_hash,
            "note": self.note,
        }

    @property
    def transcript_hash(self) -> str:
        return h(TAG_CEREMONY, canonical(self.to_dict()))


CEREMONY_NOTE = (
    "Trusted-dealer ceremony. The dealer generated the modulus from combined "
    "member entropy and states that the factors were destroyed. This is NOT "
    "multiparty generation: a dishonest dealer retains a trapdoor. Breadcrumbs "
    "is designed so that a trapdoor holder can fail a verification but cannot "
    "forge history, because every accumulator witness is checked against the "
    "Merkle proof and the block that independently commit the same record."
)


def run_ceremony(
    dealer: str,
    contributions: dict[str, bytes],
    bits: int = DEFAULT_MODULUS_BITS,
    keep_factors: bool = False,
) -> tuple[RSAGroup, CeremonyTranscript, tuple[int, int] | None]:
    """
    Combine member entropy into one modulus and record how it happened.

    Every member contributes secret bytes and publishes only their hash, so the
    transcript proves what each member put in without revealing it. If even one
    contribution is honestly random, the modulus is not predictable in advance by
    any other member — which is a weaker property than an absent trapdoor, and
    the note above says so.

    `keep_factors` exists for the attack tests and defaults to off. In a real
    ceremony this function runs once, on an air-gapped machine, and the caller
    never sees the factors at all.
    """
    if len(contributions) < 2:
        raise GroupError("a ceremony needs at least two contributors")

    seed = hashlib.sha512()
    seed.update(TAG_CEREMONY)
    for member in sorted(contributions):
        blob = contributions[member]
        seed.update(member.encode("utf-8"))
        seed.update(len(blob).to_bytes(8, "big"))
        seed.update(blob)

    p = _random_prime(bits // 2, entropy=seed.digest() + b"p")
    q = _random_prime(bits - bits // 2, entropy=seed.digest() + b"q")
    while q == p:
        q = _random_prime(bits - bits // 2, entropy=seed.digest() + b"q2")

    group = RSAGroup(
        modulus=p * q,
        generator=RSAGroup._derive_generator(p * q),
        provenance=f"consortium ceremony, {len(contributions)} contributors, dealer {dealer}",
    )
    transcript = CeremonyTranscript(
        modulus_bits=bits,
        dealer=dealer,
        contributors=sorted(contributions),
        contribution_hashes={
            m: h(TAG_CEREMONY, contributions[m]) for m in sorted(contributions)
        },
        attestations={},
        parameters_hash=group.parameters_hash,
        note=CEREMONY_NOTE,
    )
    return group, transcript, ((p, q) if keep_factors else None)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def _random_prime(bits: int, entropy: bytes | None = None) -> int:
    """
    A random prime of exactly `bits` bits.

    When `entropy` is given the search is seeded from it and therefore
    reproducible, which is what makes a ceremony auditable by its participants.
    Otherwise it draws from the system CSPRNG.
    """
    from .hashprime import is_prime

    counter = 0
    while True:
        if entropy is None:
            candidate = secrets.randbits(bits)
        else:
            raw = b""
            need = (bits + 7) // 8
            c = 0
            while len(raw) < need:
                raw += hashlib.sha512(entropy + counter.to_bytes(8, "big") + c.to_bytes(4, "big")).digest()
                c += 1
            candidate = int.from_bytes(raw[:need], "big")
        candidate |= 1 << (bits - 1)
        candidate |= 1
        if is_prime(candidate):
            return candidate
        counter += 1
        if entropy is None:
            continue
