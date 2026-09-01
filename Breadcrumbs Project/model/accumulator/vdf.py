"""
A verifiable delay function, in the same group as the accumulator.

THE PROBLEM IT SOLVES
Every timestamp in this ledger arrives as an argument from a client, because a
contract that reads a clock is not deterministic and two endorsers would
disagree. That is correct engineering and it leaves a hole: the ledger's sense of
time is only as good as the honesty of whoever supplied the timestamps. A
colluding majority could sit down on a Sunday and manufacture eight months of
plausible history, each block carrying a date it likes, and nothing in the hash
chain would object. Hash chains prove *order*. They do not prove *duration*.

A verifiable delay function does. Computing y = x^(2^T) requires T squarings that
cannot be parallelised — a thousand machines finish no sooner than one — so a
value of y with a valid proof is evidence that real, sequential time passed
between the input and the output. Fabricating a year of history then costs a
year of computation on the fastest squaring hardware in existence, which is a
much harder thing to arrange quietly than a set of agreeable clocks.

Verification is the asymmetry that makes it usable: Wesolowski's proof turns
T sequential squarings into two exponentiations by a 128-bit prime. A buyer
checks a month of elapsed time in milliseconds.

WHAT IT DOES NOT DO, SAID PLAINLY
A VDF lower-bounds elapsed time. It does not tell you the date. It cannot
distinguish "this epoch is two weeks after the last one" from "this epoch is two
weeks after the last one, and both of them happened last year". Absolute time
still has to come from outside, which is what the epoch digest in
`model/ledger/anchor.py` is for: members countersign the digest as they see it,
and an external observer's copy fixes the chain to real dates. The VDF stops
history being *compressed*; the anchor stops it being *shifted*. Neither is
sufficient alone, and a report that claimed either was would deserve the
question it would get.
"""

from __future__ import annotations

from typing import Any

from .accumulator import POE_CHALLENGE_BITS, _int_digest
from .hashprime import hash_to_prime
from .rsa_group import RSAGroup

TAG_VDF = b"breadcrumbs:vdf:v1"


class VDFError(Exception):
    """Raised when a delay proof is malformed or does not check out."""


def _challenge(group: RSAGroup, x: int, y: int, iterations: int) -> int:
    """
    Fiat-Shamir challenge, binding the input, the output, the difficulty and the
    group. Omitting `iterations` would let a prover present a short computation's
    proof as evidence of a long one, which is the only thing this construction
    is being asked to rule out.
    """
    payload = {
        "params": group.parameters_hash,
        "x": format(x, "x"),
        "y": format(y, "x"),
        "iterations": iterations,
        "digest": _int_digest(x ^ y).hex(),
    }
    prime, _ = hash_to_prime(payload, bits=POE_CHALLENGE_BITS, tag=TAG_VDF)
    return prime


def evaluate(group: RSAGroup, x: int, iterations: int) -> tuple[int, dict[str, Any]]:
    """
    Compute y = x^(2^T) and a proof of it. Returns (y, proof).

    Two passes, because the challenge cannot be known until y is: the first
    squares T times to find y, the second replays the squaring while dividing
    2^T by the challenge to build the proof. Both passes are sequential and each
    costs T squarings, so a prover pays 2T and a verifier pays 2 exponentiations.
    That ratio is the whole construction.
    """
    if iterations < 1:
        raise VDFError("a delay function needs at least one iteration")
    if not group.contains(x):
        raise VDFError("input is not a group element")

    y = group.normalise(x)
    for _ in range(iterations):
        y = group.normalise(y * y)

    ell = _challenge(group, x, y, iterations)

    # Long division of 2^T by ell, carried out alongside the squaring so that the
    # quotient never has to be materialised: it has T bits, and T is meant to be
    # large enough that a week of computing does not fit in memory.
    pi = 1
    remainder = 1
    for _ in range(iterations):
        doubled = remainder * 2
        bit = doubled // ell
        remainder = doubled % ell
        pi = group.normalise(pi * pi)
        if bit:
            pi = group.normalise(pi * pow(x, bit, group.modulus))

    return y, {
        "kind": "vdf",
        "iterations": iterations,
        "challenge_hex": format(ell, "x"),
        "proof_hex": format(group.normalise(pi), "x"),
    }


def verify(group: RSAGroup, x: int, y: int, proof: dict[str, Any]) -> tuple[bool, str]:
    """
    Check a delay proof: pi^ell * x^(2^T mod ell) == y. Returns (ok, reason).

    Constant work regardless of T. `pow(2, T, ell)` is what collapses the
    exponent — the verifier never forms 2^T, which for a week of squaring would
    be a number with more bits than there are atoms worth counting.
    """
    try:
        iterations = int(proof["iterations"])
        ell = int(proof["challenge_hex"], 16)
        pi = int(proof["proof_hex"], 16)
    except (KeyError, ValueError, TypeError):
        return False, "malformed proof"

    if iterations < 1:
        return False, "proof claims fewer than one iteration"
    if not group.contains(x) or not group.contains(y) or not group.contains(pi):
        return False, "input, output or proof is not a group element"
    if ell != _challenge(group, x, y, iterations):
        return False, "challenge does not match the statement"

    residue = pow(2, iterations, ell)
    left = group.mul(group.exp(pi, ell), group.exp(x, residue))
    if left != group.normalise(y):
        return False, "proof does not reconstruct the output"
    return True, ""


def calibrate(group: RSAGroup, target_seconds: float, sample: int = 2000) -> int:
    """
    How many iterations approximate a wall-clock delay on this machine.

    Deliberately not used inside any contract. The consortium fixes the
    difficulty by agreement and writes it into the channel configuration, because
    a difficulty derived from local timing would differ between peers and every
    endorsement would mismatch. This helper exists so that agreement can be an
    informed one, and so the report can state what a chosen T actually cost.

    The honest caveat: this measures *this* machine. An adversary with faster
    squaring hardware — and specialised VDF ASICs exist — completes the same T in
    less time. The security margin is the ratio between the fastest hardware in
    existence and the slowest honest participant, and it is a parameter to be
    reviewed, not a constant to be set once.
    """
    import time

    y = group.normalise(group.generator)
    start = time.perf_counter()
    for _ in range(sample):
        y = group.normalise(y * y)
    elapsed = time.perf_counter() - start
    if elapsed <= 0:
        raise VDFError("timing sample was too fast to measure; increase `sample`")
    return max(1, int(sample * target_seconds / elapsed))
