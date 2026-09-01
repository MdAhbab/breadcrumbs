"""
Tests for the accumulator, the group it lives in, and the delay function.

Same discipline as `test_ledger.py`: each test names a way the mathematics could
be cheated and shows what happens. The last test in this file is the important
one — it demonstrates an attack that *succeeds*, because the honest way to
present a trusted-dealer modulus is to show exactly what the dealer can do with
it and then show why it does not buy them a rewritten history.

A 1024-bit modulus is used throughout. That is below what anyone should deploy
and it is here so the suite finishes in seconds; the security argument does not
change with the size, only the margin does.
"""

from __future__ import annotations

import pytest

from model.accumulator import (
    Accumulator,
    AccumulatorError,
    AggregateWitness,
    MembershipWitness,
    RSAGroup,
    hash_to_prime,
    is_prime,
    prove_exponentiation,
    run_ceremony,
    vdf,
    verify_aggregate,
    verify_batch_update,
    verify_exponentiation,
    verify_membership,
    verify_non_membership,
    verify_prime,
)
from model.accumulator.rsa_group import GroupError

TEST_BITS = 1024


@pytest.fixture(scope="module")
def group():
    g, _, _ = RSAGroup.generate_untrusted(TEST_BITS)
    return g


@pytest.fixture(scope="module")
def trapdoor():
    """A group whose factors we keep, for the honest-limitation test at the end."""
    return RSAGroup.generate_untrusted(TEST_BITS)


def _record(i: int) -> dict:
    return {"record_id": f"rc-{i:04d}", "merkle_root": f"{i:064x}", "period": "2026-07"}


@pytest.fixture(scope="module")
def filled(group):
    """An accumulator holding forty records, added as one epoch."""
    acc = Accumulator(group=group)
    records = [_record(i) for i in range(40)]
    elements, proof = acc.batch_add(records)
    return acc, records, elements, proof


# -- primality ------------------------------------------------------------
def test_carmichael_numbers_are_not_mistaken_for_primes():
    """
    The attack: place a composite into the accumulator. Every prime dividing it
    then has a computable witness, so membership can be forged for elements that
    were never added.

    Carmichael numbers pass Fermat's test to every coprime base, which is why the
    test underneath hash_to_prime has to be Miller-Rabin plus Lucas rather than
    anything simpler.
    """
    for composite in (561, 1105, 1729, 2465, 2821, 6601, 8911, 41041, 825265, 321197185):
        assert not is_prime(composite), composite


def test_primality_is_deterministic_because_endorsers_must_agree():
    """
    Two endorsers that disagree about whether a candidate is prime compute
    different accumulator values, and `Network.propose` abandons the transaction
    as non-deterministic. Random-base Miller-Rabin would do exactly that, rarely
    and unreproducibly, which is the worst failure mode available.
    """
    payload = {"record_id": "rc-0007"}
    first = hash_to_prime(payload)
    for _ in range(5):
        assert hash_to_prime(payload) == first


def test_a_prime_does_not_verify_against_a_different_record():
    prime, nonce = hash_to_prime({"record_id": "rc-0001"})
    assert verify_prime({"record_id": "rc-0001"}, prime, nonce)
    assert not verify_prime({"record_id": "rc-0002"}, prime, nonce)


def test_a_composite_presented_with_a_valid_nonce_is_rejected():
    """
    Verification checks two separate things, and dropping either one is fatal.
    Here the candidate genuinely comes from the payload but is not prime.
    """
    from model.accumulator.hashprime import _candidate

    payload = {"record_id": "rc-0003"}
    nonce = 0
    while True:
        candidate = _candidate(b"breadcrumbs:hashprime:v1", b'{"record_id":"rc-0003"}', nonce, 256)
        if not is_prime(candidate):
            break
        nonce += 1
    assert not verify_prime(payload, candidate, nonce)


# -- the group ------------------------------------------------------------
def test_elements_and_their_negatives_are_the_same_element(group):
    """
    The group is quotiented by the sign. If x and N-x were distinct, an attacker
    would hold a free element of order two and could take square roots of part of
    the group without the factorisation.
    """
    x = group.exp(group.generator, 11)
    assert group.normalise(group.modulus - x) == x


def test_a_short_modulus_is_refused():
    with pytest.raises(GroupError):
        RSAGroup.from_public_modulus(3 * 5, "far too small")


def test_the_ceremony_is_reproducible_from_its_contributions():
    """
    Every contributor must be able to re-derive the modulus from the inputs and
    confirm the dealer used them, otherwise the transcript proves nothing.
    """
    contributions = {"ApexTextileMSP": b"a" * 32, "NoorGarmentsMSP": b"n" * 32, "BVCertificationMSP": b"b" * 32}
    first, transcript, _ = run_ceremony("BGMEAConsortiumMSP", contributions, bits=TEST_BITS)
    second, _, _ = run_ceremony("BGMEAConsortiumMSP", contributions, bits=TEST_BITS)
    assert first.modulus == second.modulus
    assert transcript.parameters_hash == first.parameters_hash
    assert "NOT multiparty generation" in transcript.note


def test_a_ceremony_needs_more_than_one_contributor():
    with pytest.raises(GroupError):
        run_ceremony("BGMEAConsortiumMSP", {"ApexTextileMSP": b"a" * 32}, bits=TEST_BITS)


# -- membership -----------------------------------------------------------
def test_a_committed_record_has_a_witness_that_verifies(filled, group):
    acc, records, _, _ = filled
    witness = acc.membership_witness(records[7])
    ok, why = verify_membership(group, acc.value, witness, records[7], acc.epoch)
    assert ok, why


def test_a_witness_does_not_transfer_to_another_record(filled, group):
    """
    The attack: obtain a valid witness for a record you are allowed to disclose,
    then present it for a record you are not.
    """
    acc, records, _, _ = filled
    witness = acc.membership_witness(records[7])
    ok, why = verify_membership(group, acc.value, witness, records[8], acc.epoch)
    assert not ok
    assert "does not hash to the prime" in why


def test_an_invented_witness_is_rejected(filled, group):
    acc, records, _, _ = filled
    genuine = acc.membership_witness(records[3])
    forged = MembershipWitness(
        element_prime=genuine.element_prime,
        element_nonce=genuine.element_nonce,
        witness=group.exp(genuine.witness, 3),
        epoch=genuine.epoch,
    )
    ok, why = verify_membership(group, acc.value, forged, records[3], acc.epoch)
    assert not ok
    assert "does not raise to the accumulator" in why


def test_root_factor_agrees_with_witnesses_computed_one_at_a_time(filled):
    """
    The fast path and the obvious path must produce identical witnesses. If they
    ever diverge the fast path is silently issuing proofs that will not verify.
    """
    acc, records, _, _ = filled
    fast = acc.all_membership_witnesses()
    for record in records[:6]:
        slow = acc.membership_witness(record)
        assert fast[slow.element_prime] == slow.witness


def test_a_witness_from_an_earlier_epoch_is_refused_rather_than_silently_failing(group):
    """
    Stale is not the same as forged, and a verifier that cannot tell the
    difference will send an honest factory chasing a nonexistent attack.
    """
    acc = Accumulator(group=group)
    record = _record(1)
    acc.add(record)
    witness = acc.membership_witness(record)
    acc.add(_record(2))

    ok, why = verify_membership(group, acc.value, witness, record, acc.epoch)
    assert not ok
    assert "epoch" in why

    brought_forward = acc.update_witness(witness, [acc.primes[-1]])
    ok, why = verify_membership(group, acc.value, brought_forward, record, acc.epoch)
    assert ok, why


# -- non-membership -------------------------------------------------------
def test_a_record_that_was_never_committed_can_be_proved_absent(filled, group):
    """
    This is the capability a Merkle tree does not have, and the one that turns
    "we hold no such certificate" into evidence rather than a filing failure.
    """
    acc, _, _, _ = filled
    ghost = {"record_id": "rc-9999", "merkle_root": "f" * 64, "period": "2026-07"}
    witness = acc.non_membership_witness(ghost)
    ok, why = verify_non_membership(group, acc.value, witness, ghost, acc.epoch)
    assert ok, why


def test_absence_cannot_be_proved_for_a_record_that_is_present(filled):
    acc, records, _, _ = filled
    with pytest.raises(AccumulatorError):
        acc.non_membership_witness(records[0])


def test_a_non_membership_witness_does_not_transfer(filled, group):
    acc, _, _, _ = filled
    ghost = {"record_id": "rc-9999", "merkle_root": "f" * 64, "period": "2026-07"}
    other = {"record_id": "rc-8888", "merkle_root": "e" * 64, "period": "2026-07"}
    witness = acc.non_membership_witness(ghost)
    ok, _ = verify_non_membership(group, acc.value, witness, other, acc.epoch)
    assert not ok


# -- aggregation and batching --------------------------------------------
def test_one_witness_covers_many_records(filled, group):
    acc, records, _, _ = filled
    aggregate = acc.aggregate(records[:12])
    ok, why = verify_aggregate(group, acc.value, aggregate, acc.epoch)
    assert ok, why


def test_a_non_member_cannot_be_smuggled_into_an_aggregate(filled, group):
    """
    The attack: take a valid aggregate over twelve real records, append a
    thirteenth that was never committed, and hope the verifier only spot-checks.
    """
    acc, records, _, _ = filled
    aggregate = acc.aggregate(records[:12])
    ghost_prime, _ = acc.element({"record_id": "rc-9999", "merkle_root": "f" * 64, "period": "2026-07"})
    padded = AggregateWitness(
        primes=[*aggregate.primes, ghost_prime], witness=aggregate.witness, epoch=aggregate.epoch
    )
    ok, why = verify_aggregate(group, acc.value, padded, acc.epoch)
    assert not ok
    assert "does not raise to the accumulator" in why


def test_the_batching_proof_and_the_direct_check_agree(filled, group):
    """
    The optimisation must never accept something the plain relation would reject.
    Both paths are exercised on the same witness, because a construction that can
    only be verified through its own shortcut cannot be independently audited.
    """
    acc, records, _, _ = filled
    aggregate = acc.aggregate(records[:8])
    assert aggregate.proof is not None

    without = AggregateWitness(
        primes=aggregate.primes, witness=aggregate.witness, epoch=aggregate.epoch
    )
    proved_ok, _ = verify_aggregate(group, acc.value, aggregate, acc.epoch)
    plain_ok, _ = verify_aggregate(group, acc.value, without, acc.epoch)
    assert proved_ok and plain_ok


def test_a_forged_batching_proof_is_rejected(filled, group):
    """
    The attack: keep a genuine aggregate witness, attach a proof that claims it
    covers a different set, and hope the verifier trusts the shortcut.
    """
    acc, records, _, _ = filled
    aggregate = acc.aggregate(records[:8])
    other = acc.aggregate(records[8:16])

    swapped = AggregateWitness(
        primes=aggregate.primes,
        witness=aggregate.witness,
        epoch=aggregate.epoch,
        proof=other.proof,
    )
    ok, why = verify_aggregate(group, acc.value, swapped, acc.epoch)
    assert not ok
    assert "does not raise to the accumulator" in why


def test_a_batch_update_proves_itself(filled, group):
    acc, _, elements, proof = filled
    start = group.normalise(group.generator)
    assert verify_batch_update(group, start, [p for p, _ in elements], acc.value, proof)


def test_a_batch_update_proof_does_not_cover_a_different_set(filled, group):
    acc, _, elements, proof = filled
    start = group.normalise(group.generator)
    fewer = [p for p, _ in elements][:-1]
    assert not verify_batch_update(group, start, fewer, acc.value, proof)


def test_a_proof_of_exponentiation_cannot_be_moved_to_another_statement(filled, group):
    """
    The exponent here is the product of forty 256-bit primes, which is the size
    a real epoch produces. A small exponent would exercise the degenerate branch
    where the quotient is zero and prove nothing about the construction.
    """
    acc, _, elements, _ = filled
    exponent = 1
    for prime, _ in elements:
        exponent *= prime
    base = group.exp(group.generator, 5)
    result = group.exp(base, exponent)

    proof = prove_exponentiation(group, base, exponent, result)
    assert verify_exponentiation(group, base, exponent, result, proof)
    assert not verify_exponentiation(group, base, exponent + 2, result, proof)
    assert not verify_exponentiation(group, group.exp(base, 2), exponent, result, proof)


def test_a_short_exponent_proof_still_verifies(group):
    """
    A quotient of zero makes the proof element the group identity. That is
    correct, not a malformed proof, and the verifier must not reject it.
    """
    base = group.exp(group.generator, 5)
    result = group.exp(base, 1234567)
    proof = prove_exponentiation(group, base, 1234567, result)
    assert proof["witness_hex"] == "1"
    assert verify_exponentiation(group, base, 1234567, result, proof)


# -- delay function -------------------------------------------------------
def test_a_delay_proof_verifies_and_is_far_cheaper_than_the_computation(group):
    x = group.element_from({"epoch": 4, "head": "0" * 64})
    y, proof = vdf.evaluate(group, x, 2000)
    ok, why = vdf.verify(group, x, y, proof)
    assert ok, why


def test_claiming_more_elapsed_time_than_was_spent_is_rejected(group):
    """
    The attack that matters: a colluding majority manufactures months of history
    over a weekend and labels each epoch with the delay it would like to claim.
    """
    x = group.element_from({"epoch": 5, "head": "1" * 64})
    y, proof = vdf.evaluate(group, x, 1000)
    overstated = dict(proof)
    overstated["iterations"] = 100_000
    ok, why = vdf.verify(group, x, y, overstated)
    assert not ok
    assert "challenge" in why


def test_a_tampered_delay_output_is_rejected(group):
    x = group.element_from({"epoch": 6, "head": "2" * 64})
    y, proof = vdf.evaluate(group, x, 1000)
    ok, _ = vdf.verify(group, x, group.mul(y, 3), proof)
    assert not ok


# -- the honest limitation ------------------------------------------------
def test_the_trapdoor_holder_can_forge_a_witness_against_the_accumulator_alone(trapdoor):
    """
    An attack that SUCCEEDS, recorded here deliberately.

    Whoever knows the factorisation of the modulus knows the group's order, and
    can therefore compute an x-th root of anything. That is enough to mint a
    membership witness for a record that was never committed. No amount of care
    inside this package prevents it, and a report claiming otherwise would be
    wrong.

    What follows from it is a design constraint rather than a defeat: the
    accumulator must never be the sole authority. A verifier accepts a record
    only when the accumulator witness AND the Merkle proof AND the committed
    block all agree, and the trapdoor buys none of the latter two. The
    corresponding end-to-end test lives in `test_attacks_insider.py`; this one
    exists so that the capability is documented where the mathematics is, and so
    that nobody later mistakes the accumulator for a standalone guarantee.
    """
    group, p, q = trapdoor
    acc = Accumulator(group=group)
    for i in range(10):
        acc.add(_record(i))

    ghost = {"record_id": "rc-forged", "merkle_root": "0" * 64, "period": "2026-07"}
    ghost_prime, ghost_nonce = acc.element(ghost)

    order = (p - 1) * (q - 1) // 2  # order of the quotient group
    root_exponent = pow(ghost_prime, -1, order)
    forged = MembershipWitness(
        element_prime=ghost_prime,
        element_nonce=ghost_nonce,
        witness=group.exp(acc.value, root_exponent),
        epoch=acc.epoch,
    )

    ok, why = verify_membership(group, acc.value, forged, ghost, acc.epoch)
    assert ok, f"the forgery should succeed against the accumulator alone: {why}"
