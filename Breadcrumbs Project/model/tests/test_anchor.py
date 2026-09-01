"""
The accumulator as the consortium enforces it, rather than as a library.

The tests that matter here are the last two. Together they are the answer to the
standard objection to RSA accumulators — "whoever knows the factorisation can
forge any witness" — which this project answers structurally rather than by
insisting the trapdoor is safe.
"""

from __future__ import annotations

import pytest

from model.accumulator import (
    Accumulator,
    MembershipWitness,
    run_ceremony,
    vdf,
    verify_membership,
)
from model.anchoring import anchor_epoch, install_group, verify_record
from model.chaincode.anchor import record_element
from model.consortium import DOCUMENT_CHANNEL, build
from model.merkle import MerkleTree

TS = "2026-08-05T09:14:00Z"
BITS = 1024


@pytest.fixture(scope="module")
def ceremony():
    """One ceremony for the whole module; generating moduli is the slow part."""
    return run_ceremony(
        "BGMEAConsortiumMSP",
        {"ApexTextileMSP": b"a" * 32, "BVCertificationMSP": b"b" * 32},
        bits=BITS,
        keep_factors=True,
    )


@pytest.fixture
def anchored(ceremony):
    """A consortium with parameters installed and three records accumulated."""
    group, transcript, factors = ceremony
    c = build()
    install_group(c, DOCUMENT_CHANNEL, group, transcript, TS)

    ids = []
    for i in range(3):
        record_id = f"rc-{i:03d}"
        rows = [{"worker_ref": f"W-{i}-{j}", "net_pay_bdt": 14000 + j} for j in range(8)]
        c.network.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_record",
            {
                "record_id": record_id, "merkle_root": MerkleTree(rows).root,
                "record_type": "payroll_register", "period": "2026-07", "site": "Gazipur",
                "row_count": len(rows), "schema_version": "v2.1.0", "timestamp": TS,
            },
            submitter=c.who("fatema.begum"),
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )
        ids.append(record_id)

    anchor_epoch(c, DOCUMENT_CHANNEL, [("record", i) for i in ids], TS)
    return c, group, factors, ids


def _witness(c, group, record_id, caller):
    """Issue a witness the way the owning factory would."""
    stored = c.network.query(
        DOCUMENT_CHANNEL, "doccustody", "get_record", {"record_id": record_id}, caller=caller
    )
    entries = sorted(
        (v for _, v in c.network.state.range(DOCUMENT_CHANNEL, "anchored:")),
        key=lambda e: (e["epoch"], e["prime_hex"]),
    )
    acc = Accumulator(group=group)
    for entry in entries:
        prime = int(entry["prime_hex"], 16)
        acc.primes.append(prime)
        acc.nonces[prime] = 0
    state = c.network.query(DOCUMENT_CHANNEL, "anchor", "get_state", {}, caller=caller)
    acc.value = int(state["value_hex"], 16)
    acc.epoch = int(state["epoch"])
    return acc.membership_witness(record_element(stored))


# -- setup ----------------------------------------------------------------
def test_parameters_and_their_ceremony_are_both_on_the_ledger(anchored):
    """
    The transcript is stored, not merely hashed. A member joining later has to be
    able to read who was in the room, and a hash of a document nobody kept is a
    gesture rather than a record.
    """
    c, group, _, _ = anchored
    stored = c.network.query(
        DOCUMENT_CHANNEL, "anchor", "get_group", {}, caller=c.who("james.holloway")
    )
    assert stored["params"]["modulus_hex"] == format(group.modulus, "x")
    assert stored["transcript"]["dealer"] == "BGMEAConsortiumMSP"
    assert "NOT multiparty generation" in stored["transcript"]["note"]


def test_parameters_cannot_be_installed_twice(anchored, ceremony):
    c, _, _, _ = anchored
    group, transcript, _ = ceremony
    with pytest.raises(Exception, match="already installed"):
        install_group(c, DOCUMENT_CHANNEL, group, transcript, TS)


# -- what may be accumulated ----------------------------------------------
def test_a_record_the_ledger_never_saw_cannot_be_accumulated(anchored):
    """
    The check that makes a membership witness mean "this was committed" rather
    than "somebody put this in the accumulator".
    """
    c, _, _, _ = anchored
    with pytest.raises(Exception, match="no committed record"):
        anchor_epoch(c, DOCUMENT_CHANNEL, [("record", "rc-invented")], TS)


def test_a_record_cannot_be_accumulated_under_someone_elses_prime(anchored, ceremony):
    """
    The attack: commit an innocuous record, then accumulate it under the prime
    belonging to a document you want witnesses for. The contract re-derives the
    element from state and re-checks the mapping, so the substitution fails.
    """
    c, group, _, ids = anchored
    caller = c.who("fatema.begum")
    real = c.network.query(
        DOCUMENT_CHANNEL, "doccustody", "get_record", {"record_id": ids[0]}, caller=caller
    )
    wrong_prime, wrong_nonce = Accumulator(group=group).element(
        {**record_element(real), "record_id": "something-else"}
    )
    state = c.network.query(DOCUMENT_CHANNEL, "anchor", "get_state", {}, caller=caller)
    with pytest.raises(Exception, match="does not hash to the prime"):
        c.network.invoke(
            DOCUMENT_CHANNEL, "anchor", "advance_epoch",
            {
                "elements": [{"kind": "record", "key": ids[0],
                              "prime_hex": format(wrong_prime, "x"), "nonce": wrong_nonce}],
                "value_hex": state["value_hex"],
                "proof": {"kind": "poe", "statement": "x", "challenge_hex": "3", "witness_hex": "1"},
                "timestamp": TS,
            },
            submitter=caller,
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )


def test_the_same_record_cannot_be_accumulated_twice(anchored):
    c, _, _, ids = anchored
    with pytest.raises(Exception, match="already accumulated"):
        anchor_epoch(c, DOCUMENT_CHANNEL, [("record", ids[0])], TS)


def test_an_accumulator_value_that_does_not_follow_is_rejected(anchored, ceremony):
    """
    The attack: submit a new accumulator value of your own choosing, so that
    witnesses you have precomputed will verify against it.
    """
    c, group, _, _ = anchored
    caller = c.who("fatema.begum")
    rows = [{"worker_ref": "W-x", "net_pay_bdt": 1}]
    c.network.invoke(
        DOCUMENT_CHANNEL, "doccustody", "commit_record",
        {
            "record_id": "rc-extra", "merkle_root": MerkleTree(rows).root,
            "record_type": "payroll_register", "period": "2026-08", "site": "Gazipur",
            "row_count": 1, "schema_version": "v2.1.0", "timestamp": TS,
        },
        submitter=caller,
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    stored = c.network.query(
        DOCUMENT_CHANNEL, "doccustody", "get_record", {"record_id": "rc-extra"}, caller=caller
    )
    prime, nonce = Accumulator(group=group).element(record_element(stored))
    state = c.network.query(DOCUMENT_CHANNEL, "anchor", "get_state", {}, caller=caller)
    chosen = group.exp(group.generator, 999983)

    from model.accumulator import prove_batch_update

    honest_proof = prove_batch_update(
        group, int(state["value_hex"], 16), [prime], chosen
    )
    with pytest.raises(Exception, match="does not show this value follows"):
        c.network.invoke(
            DOCUMENT_CHANNEL, "anchor", "advance_epoch",
            {
                "elements": [{"kind": "record", "key": "rc-extra",
                              "prime_hex": format(prime, "x"), "nonce": nonce}],
                "value_hex": format(chosen, "x"),
                "proof": honest_proof,
                "timestamp": TS,
            },
            submitter=caller,
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )


# -- the beacon -----------------------------------------------------------
def test_an_epoch_carries_a_proof_that_time_passed(anchored):
    c, group, _, _ = anchored
    caller = c.who("fatema.begum")
    digest = c.network.query(DOCUMENT_CHANNEL, "anchor", "get_digest", {"epoch": 1}, caller=caller)
    x = group.element_from({"beacon_seed": digest["parameters_hash"], "epoch": 1})
    y, proof = vdf.evaluate(group, x, 2000)

    _, result, response = c.network.invoke(
        DOCUMENT_CHANNEL, "anchor", "publish_beacon",
        {
            "epoch": 1, "output_hex": format(y, "x"), "proof": proof,
            "minimum_iterations": 1000, "timestamp": TS,
        },
        submitter=caller,
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    assert result.valid, result.reason
    assert response["iterations"] == 2000


def test_a_beacon_claiming_less_work_than_agreed_is_refused(anchored):
    """
    A consortium that agrees on an epoch's worth of delay has to be able to
    enforce it, or the beacon becomes decorative.
    """
    c, group, _, _ = anchored
    caller = c.who("fatema.begum")
    digest = c.network.query(DOCUMENT_CHANNEL, "anchor", "get_digest", {"epoch": 1}, caller=caller)
    x = group.element_from({"beacon_seed": digest["parameters_hash"], "epoch": 1})
    y, proof = vdf.evaluate(group, x, 500)
    with pytest.raises(Exception, match="less work than the consortium requires"):
        c.network.invoke(
            DOCUMENT_CHANNEL, "anchor", "publish_beacon",
            {
                "epoch": 1, "output_hex": format(y, "x"), "proof": proof,
                "minimum_iterations": 10_000, "timestamp": TS,
            },
            submitter=caller,
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )


# -- end to end, and the trapdoor -----------------------------------------
def test_a_genuine_record_verifies_through_all_three_checks(anchored):
    c, group, _, ids = anchored
    buyer = c.who("james.holloway")
    witness = _witness(c, group, ids[1], buyer)
    ok, why = verify_record(c, DOCUMENT_CHANNEL, ids[1], witness, buyer)
    assert ok, why


def test_the_trapdoor_holder_cannot_rewrite_history(anchored):
    """
    THE test this whole design is arranged around.

    The attacker holds p and q. That is enough to compute an arbitrary root and
    therefore to mint a membership witness for a record that was never committed
    — and the first assertion below confirms the forgery genuinely works against
    the accumulator, because a test that quietly failed to build the attack would
    prove nothing.

    What the trapdoor does not buy is the other two checks. There is no record on
    the ledger, so there is nothing to derive an element from; and there is no
    anchored entry, because entries are written only by an epoch the contract
    admitted. The attack degrades from "rewrites history" to "fails
    verification", which is the whole reason a trusted-dealer ceremony is
    survivable here.
    """
    c, group, factors, _ = anchored
    p, q = factors
    buyer = c.who("james.holloway")

    state = c.network.query(DOCUMENT_CHANNEL, "anchor", "get_state", {}, caller=buyer)
    accumulator_value = int(state["value_hex"], 16)

    ghost = {
        "type": "record",
        "record_id": "rc-fabricated",
        "merkle_root": "0" * 64,
        "bucket": "ApexTextileMSP|Gazipur|payroll_register|2026-07",
        "owner_msp": "ApexTextileMSP",
    }
    prime, nonce = Accumulator(group=group).element(ghost)
    order = (p - 1) * (q - 1) // 2
    forged = MembershipWitness(
        element_prime=prime,
        element_nonce=nonce,
        witness=group.exp(accumulator_value, pow(prime, -1, order)),
        epoch=int(state["epoch"]),
    )

    accepted, why = verify_membership(group, accumulator_value, forged, ghost, int(state["epoch"]))
    assert accepted, f"the forgery must actually work for this test to mean anything: {why}"

    ok, reason = verify_record(c, DOCUMENT_CHANNEL, "rc-fabricated", forged, buyer)
    assert not ok
    assert "holds no record" in reason
