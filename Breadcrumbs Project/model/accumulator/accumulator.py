"""
The set accumulator: one number that commits to every record ever written.

A Merkle tree answers one question well — "is this row in that document?" — and
`model/merkle/tree.py` will keep answering it, because it is cheap and it is what
selective disclosure needs. This file answers three questions a Merkle tree
cannot answer at all.

  Is this record in the set?          membership witness, constant size
  Was this record NEVER in the set?   non-membership witness
  Are these 500 records all in it?    one aggregate witness, not 500 proofs

The second is what makes forged evidence detectable: a buyer shown a compliance
certificate can obtain cryptographic proof that no such record was ever
committed, rather than an absence of evidence. The third is where the
computation saving lives: verifying n records costs one exponentiation instead
of n Merkle path walks, and the verifier holds one 3072-bit integer instead of n
committed roots.

HOW IT WORKS
Every record maps to a prime (see `hashprime.py`). The accumulator is the
generator raised to the product of all of them:

    A = g^(p_1 * p_2 * ... * p_n)

A membership witness for p_j is the same product with p_j left out, so raising
the witness to p_j gives A back. Nobody without the factorisation of the modulus
can compute a p_j-th root of A for a p_j that was never included, which is what
makes a forged witness infeasible. That is the strong RSA assumption, and it is
the whole security argument.

TWO THINGS TO HOLD ONTO
Witnesses go stale. Adding a record changes A, so every outstanding witness has
to be brought forward by exponentiating it by the new primes. That is cheap and
batchable, but a verifier checking a witness against the wrong epoch's
accumulator gets a failure that looks exactly like an attack. Every witness
carries the epoch it is valid for, and `verify_membership` will not silently
compare across epochs.

The accumulator is an accelerator, not the authority. See `rsa_group.py` for why
that distinction is what makes the trusted-dealer modulus survivable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from ..ledger.crypto import canonical, h
from .hashprime import TAG_PRIME, hash_to_prime, verify_prime
from .rsa_group import RSAGroup

TAG_ACC = b"breadcrumbs:accumulator:v1"
TAG_POE = b"breadcrumbs:poe:v1"

# The Fiat-Shamir challenge for a proof of exponentiation. 128 bits is the
# standard choice: forging a proof means finding a collision on this prime.
POE_CHALLENGE_BITS = 128


class AccumulatorError(Exception):
    """Raised when an element, a witness or a proof is not well formed."""


def _egcd(a: int, b: int) -> tuple[int, int, int]:
    """Extended Euclid. Returns (g, x, y) with a*x + b*y = g."""
    old_r, r = a, b
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    return old_r, old_s, old_t


def _int_digest(value: int) -> bytes:
    """SHA-256 of an integer's big-endian bytes. Used to bind large exponents."""
    n = max(1, (value.bit_length() + 7) // 8)
    return hashlib.sha256(value.to_bytes(n, "big")).digest()


# --------------------------------------------------------------------------
# Proof of exponentiation (Wesolowski)
# --------------------------------------------------------------------------
def _primes_digest(primes: list[int]) -> str:
    """
    A digest binding an ordered list of primes, without multiplying them out.

    This is what lets a batch proof be verified without ever forming the product.
    The list determines the exponent uniquely, so binding the list binds the
    statement just as tightly as binding the product would — and the verifier can
    then work modulo the challenge, one small multiplication per element, instead
    of building a multi-megabyte integer it has no other use for.
    """
    d = hashlib.sha256()
    d.update(TAG_POE)
    d.update(len(primes).to_bytes(8, "big"))
    for p in primes:
        d.update(_int_digest(p))
    return d.hexdigest()


def _poe_challenge(group: RSAGroup, base: int, result: int, statement: str) -> int:
    """
    Derive the challenge prime by Fiat-Shamir.

    It binds the base, the result, the group parameters and a digest of whatever
    fixes the exponent. Leaving the parameters out would let a prover move a
    valid proof to a different modulus; leaving the exponent out would let them
    reuse one proof for a different claim about the same two elements.
    """
    payload = {
        "params": group.parameters_hash,
        "base": format(base, "x"),
        "result": format(result, "x"),
        "statement": statement,
    }
    prime, _ = hash_to_prime(payload, bits=POE_CHALLENGE_BITS, tag=TAG_POE)
    return prime


def _exponent_statement(exponent: int) -> str:
    return "exp:" + _int_digest(exponent).hex() + f":{exponent.bit_length()}"


def prove_exponentiation(group: RSAGroup, base: int, exponent: int, result: int) -> dict[str, Any]:
    """
    Prove that base^exponent == result without the verifier doing that work.

    Worth being precise about when this pays. For one record the exponent is a
    256-bit prime and the proof saves nothing — checking directly is cheaper than
    checking a proof. It pays for an *epoch*: 50,000 records give an exponent of
    roughly 12.8 million bits, and the verifier reduces that to two exponentiations
    by a 128-bit prime plus 50,000 single-word multiplications. That is the
    difference between a verifier that needs a server and one that runs in a
    browser tab.
    """
    if exponent < 0:
        raise AccumulatorError("proof of exponentiation needs a non-negative exponent")
    return _prove(group, base, exponent, result, _exponent_statement(exponent))


def _prove(group: RSAGroup, base: int, exponent: int, result: int, statement: str) -> dict[str, Any]:
    """Shared body: the prover always has the exponent, whatever fixes it."""
    ell = _poe_challenge(group, base, result, statement)
    quotient = exponent // ell
    return {
        "kind": "poe",
        "statement": statement,
        "challenge_hex": format(ell, "x"),
        "witness_hex": format(group.exp(base, quotient), "x"),
    }


def verify_exponentiation(
    group: RSAGroup, base: int, exponent: int, result: int, proof: dict[str, Any]
) -> bool:
    """Check a proof of exponentiation. Two small exponentiations, whatever the exponent."""
    return _check(group, base, exponent % _safe_ell(proof), result, proof, _exponent_statement(exponent))


def _safe_ell(proof: dict[str, Any]) -> int:
    """The claimed challenge, used only to reduce the exponent; verified in `_check`."""
    try:
        ell = int(proof["challenge_hex"], 16)
    except (KeyError, ValueError, TypeError):
        return 1
    return ell if ell > 1 else 1


def _check(
    group: RSAGroup, base: int, residue: int, result: int, proof: dict[str, Any], statement: str
) -> bool:
    """The one place a proof of exponentiation is judged."""
    try:
        ell = int(proof["challenge_hex"], 16)
        pi = int(proof["witness_hex"], 16)
    except (KeyError, ValueError, TypeError):
        return False
    if proof.get("statement") != statement:
        return False
    if ell != _poe_challenge(group, base, result, statement):
        return False
    if not group.contains(pi):
        return False
    return group.mul(group.exp(pi, ell), group.exp(base, residue)) == group.normalise(result)


def prove_batch_update(
    group: RSAGroup, base: int, primes: list[int], result: int
) -> dict[str, Any]:
    """Prove base^(product of primes) == result, binding the list rather than the product."""
    exponent = 1
    for p in primes:
        exponent *= p
    return _prove(group, base, exponent, result, _primes_digest(primes))


def verify_batch_update(
    group: RSAGroup,
    previous: int,
    primes: list[int],
    current: int,
    proof: dict[str, Any],
) -> bool:
    """
    Verify one epoch's accumulator update from the list of primes added.

    The trick that makes this cheap is that the verifier never forms the product.
    It needs the exponent only modulo the 128-bit challenge, and a product modulo
    a small number is a product of small numbers — n single-word multiplications
    rather than n multiplications of a growing multi-megabyte integer. The
    challenge itself is bound to a digest of the full product, which the verifier
    computes once by a different route, so the shortcut does not weaken the
    binding.
    """
    if not primes:
        return group.normalise(previous) == group.normalise(current)
    statement = _primes_digest(primes)
    ell = _safe_ell(proof)
    residue = 1
    for p in primes:
        residue = residue * (p % ell) % ell
    return _check(group, previous, residue, current, proof, statement)


# --------------------------------------------------------------------------
# Witnesses
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class MembershipWitness:
    """
    Proof that one element is in the accumulator at a stated epoch.

    The epoch is not metadata. A witness is only valid against the accumulator
    value of the epoch it was issued for, and comparing it against a later value
    fails in a way indistinguishable from forgery. Carrying the epoch turns a
    confusing failure into a clear one: stale, not forged.
    """

    element_prime: int
    element_nonce: int
    witness: int
    epoch: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "membership",
            "prime_hex": format(self.element_prime, "x"),
            "nonce": self.element_nonce,
            "witness_hex": format(self.witness, "x"),
            "epoch": self.epoch,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MembershipWitness:
        return cls(
            element_prime=int(d["prime_hex"], 16),
            element_nonce=int(d["nonce"]),
            witness=int(d["witness_hex"], 16),
            epoch=int(d["epoch"]),
        )


@dataclass(frozen=True)
class NonMembershipWitness:
    """
    Proof that an element is NOT in the accumulator.

    This is the one a Merkle tree cannot give you, and the one that turns
    "we have no record of that certificate" from a filing failure into a
    cryptographic statement. It is a Bezout pair: since the element's prime
    shares no factor with the product of everything accumulated, there exist
    integers a and b with a*product + b*prime = 1, and publishing g^a alongside b
    proves it without revealing the product.
    """

    element_prime: int
    element_nonce: int
    coefficient: int  # b, the Bezout coefficient on the element's prime
    base: int         # g^a
    epoch: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "non_membership",
            "prime_hex": format(self.element_prime, "x"),
            "nonce": self.element_nonce,
            "coefficient": str(self.coefficient),
            "base_hex": format(self.base, "x"),
            "epoch": self.epoch,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NonMembershipWitness:
        return cls(
            element_prime=int(d["prime_hex"], 16),
            element_nonce=int(d["nonce"]),
            coefficient=int(d["coefficient"]),
            base=int(d["base_hex"], 16),
            epoch=int(d["epoch"]),
        )


@dataclass(frozen=True)
class AggregateWitness:
    """
    One witness standing in for many, with a proof that shortcuts checking it.

    Without `proof`, verifying costs one exponentiation by the product of every
    prime covered — which is linear in the number of records and, measured, ends
    up slower than simply checking that many Merkle proofs. That is not a good
    enough answer, and the batching proof is what fixes it: two exponentiations
    by a 128-bit prime and one small multiplication per record, regardless of how
    many records the witness covers.

    `proof` is optional because a verifier must be able to fall back to checking
    the relation directly. A construction that can only be verified through its
    own optimisation is one nobody can independently audit.
    """

    primes: list[int]
    witness: int
    epoch: int
    proof: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "aggregate",
            "primes_hex": [format(p, "x") for p in self.primes],
            "witness_hex": format(self.witness, "x"),
            "epoch": self.epoch,
            "proof": self.proof,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AggregateWitness:
        return cls(
            primes=[int(p, 16) for p in d["primes_hex"]],
            witness=int(d["witness_hex"], 16),
            epoch=int(d["epoch"]),
            proof=d.get("proof"),
        )


# --------------------------------------------------------------------------
# Stateless verification — everything a buyer or auditor needs
# --------------------------------------------------------------------------
def verify_membership(
    group: RSAGroup, accumulator: int, witness: MembershipWitness, payload: Any, epoch: int
) -> tuple[bool, str]:
    """
    Check a membership witness. Returns (ok, reason).

    Note what the verifier holds: the group parameters and one integer. Not the
    chain, not the world state, not a list of committed roots. That is the
    stateless-verification property, and it is what makes it realistic for a
    European buyer to check a Bangladeshi factory's records without running a
    peer.
    """
    if witness.epoch != epoch:
        return False, f"witness is for epoch {witness.epoch}, accumulator is at epoch {epoch}"
    if not verify_prime(payload, witness.element_prime, witness.element_nonce, tag=TAG_PRIME):
        return False, "the element does not hash to the prime it claims"
    if not group.contains(witness.witness):
        return False, "witness is not a group element"
    if group.exp(witness.witness, witness.element_prime) != group.normalise(accumulator):
        return False, "witness does not raise to the accumulator"
    return True, ""


def verify_non_membership(
    group: RSAGroup, accumulator: int, witness: NonMembershipWitness, payload: Any, epoch: int
) -> tuple[bool, str]:
    """
    Check a non-membership witness: A^a * (g^b)^x == g.

    A passing check says something strong and narrow: this element was never
    accumulated up to this epoch. It says nothing about later epochs, which is
    why the epoch travels with the witness and is compared here.
    """
    if witness.epoch != epoch:
        return False, f"witness is for epoch {witness.epoch}, accumulator is at epoch {epoch}"
    if not verify_prime(payload, witness.element_prime, witness.element_nonce, tag=TAG_PRIME):
        return False, "the element does not hash to the prime it claims"
    if not group.contains(witness.base):
        return False, "witness base is not a group element"
    left = group.mul(
        group.exp(accumulator, witness.coefficient),
        group.exp(witness.base, witness.element_prime),
    )
    if left != group.normalise(group.generator):
        return False, "Bezout relation does not hold; the element may in fact be a member"
    return True, ""


def verify_aggregate(
    group: RSAGroup, accumulator: int, witness: AggregateWitness, epoch: int
) -> tuple[bool, str]:
    """
    Check one witness covering many elements.

    Cost is one exponentiation by the product of the primes, against n
    exponentiations if each were checked separately — and against n Merkle path
    walks plus n committed roots in the design this replaces.
    """
    if witness.epoch != epoch:
        return False, f"witness is for epoch {witness.epoch}, accumulator is at epoch {epoch}"
    if not witness.primes:
        return False, "an aggregate witness must cover at least one element"
    if len(set(witness.primes)) != len(witness.primes):
        return False, "duplicate elements in an aggregate witness"
    if not group.contains(witness.witness):
        return False, "witness is not a group element"

    if witness.proof is not None:
        if not verify_batch_update(group, witness.witness, witness.primes, accumulator, witness.proof):
            return False, "aggregate witness does not raise to the accumulator"
        return True, ""

    product = 1
    for p in witness.primes:
        product *= p
    if group.exp(witness.witness, product) != group.normalise(accumulator):
        return False, "aggregate witness does not raise to the accumulator"
    return True, ""


# --------------------------------------------------------------------------
# The manager side — holds the set, issues witnesses
# --------------------------------------------------------------------------
@dataclass
class Accumulator:
    """
    The writer's view: the accumulator value plus the primes behind it.

    A verifier never needs this object. Each organisation runs one for its own
    channel so it can issue witnesses; the ledger stores only `value` and
    `epoch`. Keeping the primes in memory is fine at prototype scale and is the
    obvious thing to move to the world state when it is not.
    """

    group: RSAGroup
    value: int = 0
    epoch: int = 0
    primes: list[int] = field(default_factory=list)
    nonces: dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.value == 0:
            self.value = self.group.normalise(self.group.generator)

    # -- adding -----------------------------------------------------------
    def element(self, payload: Any) -> tuple[int, int]:
        """Map a record to its prime and the nonce that proves the mapping."""
        return hash_to_prime(payload, tag=TAG_PRIME)

    def add(self, payload: Any) -> tuple[int, int]:
        """Add one record. Returns (prime, nonce). Advances the epoch."""
        prime, nonce = self.element(payload)
        if prime in self.nonces:
            raise AccumulatorError("element is already accumulated")
        self.value = self.group.exp(self.value, prime)
        self.primes.append(prime)
        self.nonces[prime] = nonce
        self.epoch += 1
        return prime, nonce

    def batch_add(self, payloads: list[Any]) -> tuple[list[tuple[int, int]], dict[str, Any]]:
        """
        Add many records as one epoch, with a proof of the update.

        This is the mechanism that takes a factory from one ledger transaction
        per document to one per epoch. Every record still gets its own witness;
        what collapses is the number of times the chain has to be written to.
        """
        elements = [self.element(p) for p in payloads]
        primes = [e[0] for e in elements]
        if len(set(primes)) != len(primes):
            raise AccumulatorError("duplicate elements in a batch")
        for p in primes:
            if p in self.nonces:
                raise AccumulatorError("element is already accumulated")

        previous = self.value
        product = 1
        for p in primes:
            product *= p
        self.value = self.group.exp(previous, product)
        proof = prove_batch_update(self.group, previous, primes, self.value)
        for prime, nonce in elements:
            self.primes.append(prime)
            self.nonces[prime] = nonce
        self.epoch += 1
        return elements, proof

    # -- issuing witnesses -------------------------------------------------
    def membership_witness(self, payload: Any) -> MembershipWitness:
        """
        Issue a witness for one record. Cost is one exponentiation over the rest
        of the set — use `all_membership_witnesses` when you need many.
        """
        prime, nonce = self.element(payload)
        if prime not in self.nonces:
            raise AccumulatorError("element is not in the accumulator")
        product = 1
        for p in self.primes:
            if p != prime:
                product *= p
        return MembershipWitness(
            element_prime=prime,
            element_nonce=nonce,
            witness=self.group.exp(self.group.generator, product),
            epoch=self.epoch,
        )

    def all_membership_witnesses(self) -> dict[int, int]:
        """
        Every witness at once, by the RootFactor recursion.

        Issuing n witnesses one at a time costs n exponentiations by an
        (n-1)-prime product: quadratic in the size of the set, and unusable past
        a few thousand records. Splitting the set in half and recursing costs
        n log n, and it is the difference between a factory being able to hand
        out proofs for a year of payroll and not.
        """
        return dict(zip(self.primes, _root_factor(self.group, self.group.generator, self.primes), strict=True))

    def non_membership_witness(self, payload: Any) -> NonMembershipWitness:
        """
        Issue a proof that a record was never accumulated.

        Fails loudly if the element *is* a member, rather than returning
        something that will not verify. A caller that gets a witness back has a
        statement it can rely on.
        """
        prime, nonce = self.element(payload)
        if prime in self.nonces:
            raise AccumulatorError("element is in the accumulator; there is no proof of absence")
        product = 1
        for p in self.primes:
            product *= p
        g, a, b = _egcd(product, prime)
        if g != 1:
            raise AccumulatorError("element shares a factor with the set; the mapping is broken")
        return NonMembershipWitness(
            element_prime=prime,
            element_nonce=nonce,
            coefficient=a,
            base=self.group.exp(self.group.generator, b),
            epoch=self.epoch,
        )

    def aggregate(self, payloads: list[Any]) -> AggregateWitness:
        """
        One witness for many records, folded pairwise by Shamir's trick.

        Given witnesses for x and y, the pair (a, b) with a*x + b*y = 1 combines
        them into a single element that raises to the accumulator under x*y. Fold
        that across a list and 500 proofs become one.
        """
        primes: list[int] = []
        for payload in payloads:
            prime, _ = self.element(payload)
            if prime not in self.nonces:
                raise AccumulatorError("cannot aggregate an element that is not a member")
            primes.append(prime)
        if len(set(primes)) != len(primes):
            raise AccumulatorError("duplicate elements in an aggregate")

        witnesses = self.all_membership_witnesses()
        current_w = witnesses[primes[0]]
        current_x = primes[0]
        for prime in primes[1:]:
            current_w = _shamir(self.group, current_w, current_x, witnesses[prime], prime)
            current_x *= prime
        return AggregateWitness(
            primes=primes,
            witness=current_w,
            epoch=self.epoch,
            proof=prove_batch_update(self.group, current_w, primes, self.value),
        )

    def update_witness(self, witness: MembershipWitness, added_primes: list[int]) -> MembershipWitness:
        """
        Bring a stale witness forward across epochs.

        One exponentiation by the product of everything added since, whatever the
        gap. A holder that has been offline for a year pays the same as one that
        missed a day, which is the property that makes offline verification
        practical.
        """
        product = 1
        for p in added_primes:
            product *= p
        return MembershipWitness(
            element_prime=witness.element_prime,
            element_nonce=witness.element_nonce,
            witness=self.group.exp(witness.witness, product),
            epoch=self.epoch,
        )

    # -- state -------------------------------------------------------------
    def state(self) -> dict[str, Any]:
        """What goes on the ledger: the value, the epoch, the parameters. Not the set."""
        return {
            "value_hex": format(self.value, "x"),
            "epoch": self.epoch,
            "size": len(self.primes),
            "parameters_hash": self.group.parameters_hash,
        }

    @property
    def state_hash(self) -> str:
        return h(TAG_ACC, canonical(self.state()))


def _shamir(group: RSAGroup, w_x: int, x: int, w_y: int, y: int) -> int:
    """Combine two membership witnesses into one covering both elements."""
    g, a, b = _egcd(x, y)
    if g != 1:
        raise AccumulatorError("cannot aggregate witnesses for elements that share a factor")
    return group.mul(group.exp(w_x, b), group.exp(w_y, a))


def _root_factor(group: RSAGroup, base: int, primes: list[int]) -> list[int]:
    """
    RootFactor: all n exclusion-products in O(n log n) exponentiations.

    Iterative rather than recursive so that a factory with a hundred thousand
    records does not hit Python's recursion limit halfway through issuing a
    year of proofs.
    """
    if not primes:
        return []
    if len(primes) == 1:
        return [base]

    results: list[int | None] = [None] * len(primes)
    stack: list[tuple[int, int, int]] = [(base, 0, len(primes))]
    while stack:
        current, lo, hi = stack.pop()
        if hi - lo == 1:
            results[lo] = current
            continue
        mid = (lo + hi) // 2
        left_product = 1
        for p in primes[lo:mid]:
            left_product *= p
        right_product = 1
        for p in primes[mid:hi]:
            right_product *= p
        stack.append((group.exp(current, right_product), lo, mid))
        stack.append((group.exp(current, left_product), mid, hi))
    return [r for r in results if r is not None]
