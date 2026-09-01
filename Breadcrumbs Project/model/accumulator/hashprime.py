"""
Deterministic hash-to-prime, and the primality test underneath it.

An RSA accumulator does not accumulate records. It accumulates *primes*, one per
record, because the security argument needs the exponents to be coprime: a
membership witness for x is the accumulator with x's prime divided out, and that
division is only well defined when no other element shares the factor. So every
record has to be mapped to a prime, deterministically, by anybody who holds the
record.

Two properties matter here and both are easy to get wrong.

DETERMINISM. This runs inside chaincode. Every endorsing peer maps the same
record to the same prime or their accumulator states diverge, `Network.propose`
sees different write sets, and the transaction is abandoned as non-deterministic.
That rules out the obvious implementation. `gmpy2.is_prime` and Python's own
`random`-seeded Miller-Rabin pick *random* bases, so two peers can disagree about
whether a borderline composite is prime. Every base in this file is fixed.

ADVERSARIAL INPUT. The number being tested is derived from data an attacker
chooses. Fixed-base Miller-Rabin is exactly the setting where that is dangerous:
for any finite set of bases a composite can be constructed that passes all of
them (Arnault, 1995), and an attacker who can place a composite into the
accumulator can forge membership for anything dividing it. So the test here is
Baillie-PSW: Miller-Rabin to a set of fixed bases, *plus* a strong Lucas test.
No BPSW pseudoprime is known, and finding one is an open problem carrying a
standing prize. That is the strongest deterministic test available.

There is an asymmetry here but it is a modest one, and the benchmark says so
rather than the docstring. Finding a 256-bit prime searches roughly ninety
candidates, almost all of which trial division rejects immediately. Checking one
costs a single hash plus a full Baillie-PSW test, which cannot be skipped: a
verifier that trusts the writer's word that the exponent is prime is a verifier
that can be handed a composite. Measured, the search costs about twice the check,
not orders of magnitude. Where the real saving lives is one layer up, in the
batching proof in `accumulator.py`.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..ledger.crypto import canonical

TAG_PRIME = b"breadcrumbs:hashprime:v1"

# Every odd prime below 1000. Trial division against these removes roughly 92%
# of candidates for the cost of a few divisions, long before the expensive tests.
_SMALL_PRIMES: list[int] = []
_sieve = bytearray([1]) * 1000
_sieve[0] = _sieve[1] = 0
for _i in range(2, 1000):
    if _sieve[_i]:
        _SMALL_PRIMES.append(_i)
        for _j in range(_i * _i, 1000, _i):
            _sieve[_j] = 0
del _sieve

# Fixed Miller-Rabin bases. The first thirteen primes are a *proof* of primality
# below 3.3 x 10^24; above that they are strong evidence, and the Lucas test
# below is what carries the weight.
_MR_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def _miller_rabin(n: int, base: int) -> bool:
    """One Miller-Rabin round to a fixed base."""
    if n % base == 0:
        return n == base
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    x = pow(base, d, n)
    if x == 1 or x == n - 1:
        return True
    for _ in range(r - 1):
        x = x * x % n
        if x == n - 1:
            return True
    return False


def _jacobi(a: int, n: int) -> int:
    """Jacobi symbol (a/n) for odd n > 0. Needed to pick the Lucas parameters."""
    a %= n
    result = 1
    while a:
        while a % 2 == 0:
            a //= 2
            if n % 8 in (3, 5):
                result = -result
        a, n = n, a
        if a % 4 == 3 and n % 4 == 3:
            result = -result
        a %= n
    return result if n == 1 else 0


def _strong_lucas_prp(n: int) -> bool:
    """
    Strong Lucas probable-prime test with Selfridge's parameter choice.

    This is the half of Baillie-PSW that a crafted Miller-Rabin pseudoprime
    cannot also satisfy, because the two tests fail on structurally different
    composites. Running only the first is the mistake this file exists to avoid.
    """
    # Selfridge: the first D in 5, -7, 9, -11, ... with Jacobi (D/n) = -1.
    d = 5
    while True:
        j = _jacobi(d, n)
        if j == -1:
            break
        if j == 0 and abs(d) != n:
            return False
        if d > 0:
            d = -(d + 2)
        else:
            d = -(d - 2)
        if abs(d) > 1_000_000:  # n is almost certainly a perfect square
            return False

    p, q = 1, (1 - d) // 4

    # Factor n + 1 = s * 2^r with s odd.
    s = n + 1
    r = 0
    while s % 2 == 0:
        s //= 2
        r += 1

    # Compute the Lucas sequence (U_s, V_s) by binary ladder.
    u, v, q_k = 1, p, q
    for bit in bin(s)[3:]:
        u, v = u * v % n, (v * v - 2 * q_k) % n
        q_k = q_k * q_k % n
        if bit == "1":
            u, v = ((p * u + v) * (n + 1) // 2) % n, ((d * u + p * v) * (n + 1) // 2) % n
            q_k = q_k * q % n

    if u == 0 or v == 0:
        return True
    for _ in range(r - 1):
        v = (v * v - 2 * q_k) % n
        if v == 0:
            return True
        q_k = q_k * q_k % n
    return False


def is_prime(n: int) -> bool:
    """
    Deterministic primality test: trial division, fixed-base Miller-Rabin, Lucas.

    Deterministic in the sense that matters for consensus — the same input gives
    the same answer on every machine, every time, with no randomness anywhere.
    """
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n == p:
            return True
        if n % p == 0:
            return False
    for base in _MR_BASES:
        if not _miller_rabin(n, base):
            return False
    return _strong_lucas_prp(n)


def _candidate(tag: bytes, payload: bytes, nonce: int, bits: int) -> int:
    """
    Derive one odd candidate of exactly `bits` bits from (payload, nonce).

    The top bit is forced so the prime has a known size — a shorter exponent
    would still be a valid accumulator element but it weakens the security
    argument, which assumes the primes are large enough that guessing one is
    infeasible. The bottom bit is forced because no even candidate is worth
    testing.
    """
    out = b""
    counter = 0
    need = (bits + 7) // 8
    while len(out) < need:
        d = hashlib.sha256()
        d.update(tag)
        d.update(len(payload).to_bytes(8, "big"))
        d.update(payload)
        d.update(nonce.to_bytes(8, "big"))
        d.update(counter.to_bytes(4, "big"))
        out += d.digest()
        counter += 1
    n = int.from_bytes(out[:need], "big")
    n |= 1 << (bits - 1)  # exact bit length
    n |= 1                # odd
    return n


def hash_to_prime(payload: Any, bits: int = 256, tag: bytes = TAG_PRIME) -> tuple[int, int]:
    """
    Map any JSON-serialisable object to a prime. Returns (prime, nonce).

    The nonce is not a secret and not a salt. It is the search receipt: it says
    which candidate ended the search, so a verifier reproduces the answer with
    one hash instead of repeating the search. Publish it with the prime.
    """
    data = canonical(payload)
    nonce = 0
    while True:
        c = _candidate(tag, data, nonce, bits)
        if is_prime(c):
            return c, nonce
        nonce += 1


def verify_prime(
    payload: Any, prime: int, nonce: int, bits: int = 256, tag: bytes = TAG_PRIME
) -> bool:
    """
    Check that `prime` really is what `payload` maps to under `nonce`.

    Both halves are required. Recomputing the candidate proves the prime belongs
    to this payload; testing primality proves it is usable as an exponent. An
    implementation that checks only the first accepts a composite, and a
    composite exponent is a forged membership proof waiting to happen.
    """
    if prime.bit_length() != bits or nonce < 0:
        return False
    if _candidate(tag, canonical(payload), nonce, bits) != prime:
        return False
    return is_prime(prime)
