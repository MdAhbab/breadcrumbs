"""
Attacks by an adversary sitting on the network.

The threat model: someone who can observe, modify, delay, drop and replay
messages between organisations, but who holds no valid certificate and no private
key. In a permissioned system this is the weaker of the two adversaries — the
insider in `test_attacks_insider.py` is the dangerous one — but it is the adversary
every deployment definitely has, and the one whose defences are easiest to get
subtly wrong.

Every test names what is being intercepted and where the refusal comes from.
"""

from __future__ import annotations

import pytest

from model.accumulator import Accumulator, RSAGroup, run_ceremony
from model.anchoring import anchor_epoch, install_group
from model.consortium import DOCUMENT_CHANNEL, GATE_ORGS, MODEL_CHANNEL, build
from model.ledger.crypto import sign
from model.ledger.digest import DigestRegistry, attest, epoch_digest
from model.ledger.suites import ED25519
from model.merkle import MerkleTree

TS = "2026-08-05T09:14:00Z"


def _commit_args(record_id: str, rows: int = 8):
    body = [{"worker_ref": f"W-{i}", "net_pay_bdt": 14000 + i} for i in range(rows)]
    return {
        "record_id": record_id,
        "merkle_root": MerkleTree(body).root,
        "record_type": "payroll_register",
        "period": "2026-07",
        "site": "Gazipur",
        "row_count": rows,
        "schema_version": "v2.1.0",
        "timestamp": TS,
    }


# -- tampering in flight --------------------------------------------------
def test_altering_a_write_set_in_flight_invalidates_the_transaction():
    """
    The attack: intercept an endorsed transaction on its way to the ordering
    service and change what it writes — here, the Merkle root of a payroll
    register, so a different document would later verify against it.

    The endorsers signed the read and write sets, not merely the arguments. That
    is the design decision that stops this, and it is why `Transaction.payload`
    includes them.
    """
    c = build()
    tx = c.network.propose(
        DOCUMENT_CHANNEL, "doccustody", "commit_record", _commit_args("rc-001"),
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )

    tx.write_set[0].value = {**tx.write_set[0].value, "merkle_root": "0" * 64}

    ok, _ = c.network.submit(tx)
    assert ok
    c.network.commit(TS, channel_name=DOCUMENT_CHANNEL)
    result = c.network.channels[DOCUMENT_CHANNEL].validation[tx.tx_id]
    assert not result.valid
    assert result.code == "ENDORSEMENT_POLICY_FAILURE"


def test_an_endorsement_cannot_be_moved_to_another_transaction():
    """
    The attack: harvest genuine endorsements from a transaction the attacker was
    allowed to see, and attach them to one it wrote itself.
    """
    c = build()
    genuine = c.network.propose(
        DOCUMENT_CHANNEL, "doccustody", "commit_record", _commit_args("rc-001"),
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    forged = c.network.propose(
        DOCUMENT_CHANNEL, "doccustody", "commit_record", _commit_args("rc-002", rows=99),
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    forged.endorsements = genuine.endorsements

    ok, why = c.network.validator.check(
        forged.payload(), forged.endorsements, c.network.chaincodes["doccustody"].policy
    )
    assert not ok
    assert "not satisfied" in why


def test_a_signature_from_a_weaker_suite_does_not_pass_as_an_rsa_endorsement():
    """
    The downgrade attack: substitute a signature made under a different algorithm
    and hope the verifier takes the algorithm from something the attacker
    controls. It cannot — `suite_for_key` reads it off the key in the validated
    certificate, and an Ed25519 signature checked against an RSA key is refused
    rather than misinterpreted.
    """
    c = build()
    tx = c.network.propose(
        DOCUMENT_CHANNEL, "doccustody", "commit_record", _commit_args("rc-001"),
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    weak_key = ED25519.generate()
    tx.endorsements[0].signature = sign(weak_key, tx.payload())

    ok, why = c.network.validator.check(
        tx.payload(), tx.endorsements, c.network.chaincodes["doccustody"].policy
    )
    assert not ok
    assert "signature does not verify" in why


def test_replaying_a_committed_transaction_does_not_apply_it_twice():
    """
    The attack: capture a valid transaction off the wire and submit it again.
    Audit finding F-3; the regression lives in `test_ledger.py` and this is the
    network-adversary framing of the same defence.
    """
    c = build()
    _, first, _ = c.network.invoke(
        DOCUMENT_CHANNEL, "doccustody", "commit_record", _commit_args("rc-001"),
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    assert first.valid

    replay = c.network.propose(
        DOCUMENT_CHANNEL, "doccustody", "commit_record", _commit_args("rc-002"),
        submitter=c.who("fatema.begum"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    c.network.submit(replay)
    c.network.commit(TS, channel_name=DOCUMENT_CHANNEL)
    c.network.submit(replay)
    c.network.commit(TS, channel_name=DOCUMENT_CHANNEL)
    assert c.network.channels[DOCUMENT_CHANNEL].validation[replay.tx_id].code == "DUPLICATE_TXID"


# -- accumulator traffic --------------------------------------------------
@pytest.fixture(scope="module")
def ceremony():
    return run_ceremony(
        "BGMEAConsortiumMSP",
        {"ApexTextileMSP": b"a" * 32, "BVCertificationMSP": b"b" * 32},
        bits=1024,
        keep_factors=False,
    )


def test_an_epoch_proof_cannot_be_replayed_over_a_different_set_of_records(ceremony):
    """
    The attack: capture the proof of exponentiation from a legitimate epoch and
    attach it to an epoch that folds in a different set of records, so records the
    consortium never admitted appear to be accumulated.

    The challenge is derived by Fiat-Shamir from the element list, so a proof and
    a list that do not belong together produce a different challenge and fail.
    """
    group, transcript, _ = ceremony
    c = build()
    install_group(c, DOCUMENT_CHANNEL, group, transcript, TS)

    ids = []
    for i in range(4):
        record_id = f"rc-{i:03d}"
        c.network.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_record", _commit_args(record_id),
            submitter=c.who("fatema.begum"),
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )
        ids.append(record_id)

    anchor_epoch(c, DOCUMENT_CHANNEL, [("record", ids[0]), ("record", ids[1])], TS)

    caller = c.who("fatema.begum")
    digest = c.network.query(DOCUMENT_CHANNEL, "anchor", "get_digest", {"epoch": 1}, caller=caller)
    captured = None
    for _, tx in [(0, t) for b in c.network.channels[DOCUMENT_CHANNEL].blocks for t in b.transactions]:
        if tx.function == "advance_epoch":
            captured = tx.args["proof"]
    assert captured is not None, "the proof should have been observable on the wire"

    state = c.network.query(DOCUMENT_CHANNEL, "anchor", "get_state", {}, caller=caller)
    stored = c.network.query(
        DOCUMENT_CHANNEL, "doccustody", "get_record", {"record_id": ids[2]}, caller=caller
    )
    from model.chaincode.anchor import record_element

    prime, nonce = Accumulator(group=RSAGroup.from_dict(
        c.network.query(DOCUMENT_CHANNEL, "anchor", "get_group", {}, caller=caller)["params"]
    )).element(record_element(stored))

    with pytest.raises(Exception, match="does not show this value follows"):
        c.network.invoke(
            DOCUMENT_CHANNEL, "anchor", "advance_epoch",
            {
                "elements": [
                    {"kind": "record", "key": ids[2], "prime_hex": format(prime, "x"), "nonce": nonce}
                ],
                "value_hex": state["value_hex"],
                "proof": captured,
                "timestamp": TS,
            },
            submitter=caller,
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )
    assert digest["epoch"] == 1


# -- digest gossip --------------------------------------------------------
def test_a_gossiped_digest_cannot_be_replayed_under_a_different_epoch():
    """
    The attack: capture a member's signed digest for epoch 4 and re-present it as
    its view of epoch 5, manufacturing agreement about an epoch it never saw.

    The epoch is inside what was signed, so changing it breaks the signature.
    """
    c = build()
    registry = DigestRegistry(msp=c.msp)
    genuine = attest(
        c.who("james.holloway"),
        epoch_digest(DOCUMENT_CHANNEL, 4, "aaa", 4, "1" * 64, "f" * 64),
        TS,
    )
    moved = type(genuine)(
        msp_id=genuine.msp_id,
        identity_id=genuine.identity_id,
        certificate_pem=genuine.certificate_pem,
        digest={**genuine.digest, "epoch": 5},
        signature=genuine.signature,
        observed_at=TS,
    )
    ok, reason = registry.observe(moved)
    assert not ok
    assert "signature does not verify" in reason


def test_dropping_a_members_digest_cannot_hide_a_fork_from_the_others():
    """
    The attack: a network adversary suppresses the one digest that would reveal a
    fork. It works — for exactly as long as that member never speaks to anyone
    else. This test records the property the design actually has: detection needs
    only that ONE honest pair of members eventually compares notes, not that every
    message arrives.
    """
    c = build()
    suppressed = DigestRegistry(msp=c.msp)
    honest = epoch_digest(DOCUMENT_CHANNEL, 6, "aaa", 6, "1" * 64, "f" * 64)
    rewritten = epoch_digest(DOCUMENT_CHANNEL, 6, "bbb", 6, "2" * 64, "f" * 64)

    suppressed.observe(attest(c.who("james.holloway"), honest, TS))
    assert suppressed.fork_at(DOCUMENT_CHANNEL, 6) is None, "with one view there is nothing to compare"

    suppressed.observe(attest(c.who("meera.nair"), rewritten, TS))
    assert suppressed.fork_at(DOCUMENT_CHANNEL, 6) is not None


# -- the gate -------------------------------------------------------------
def test_swapping_a_benchmark_between_commitment_and_reveal_is_caught():
    """
    The attack: the benchmark is committed by hash before a round and revealed
    afterwards. Substitute an easier set at reveal time and every model looks
    better than it was.
    """
    from model.ledger.crypto import TAG_BENCH, hash_object

    c = build()
    admin = c.who("rafiqul.islam")
    endorsers = c.endorsers(GATE_ORGS[:3])
    real = {"task": "wage_register_inconsistency", "rows": 600}

    c.network.invoke(
        MODEL_CHANNEL, "fedmodel", "commit_benchmark",
        {
            "task_id": "wage_register_inconsistency",
            "benchmark_hash": hash_object(TAG_BENCH, real),
            "contributors": ["NoorGarmentsMSP"], "size": 600, "timestamp": TS,
        },
        admin, endorsers, TS,
    )
    with pytest.raises(Exception, match="revealed contents hash to"):
        c.network.invoke(
            MODEL_CHANNEL, "fedmodel", "reveal_benchmark",
            {
                "task_id": "wage_register_inconsistency",
                "contents": {"task": "wage_register_inconsistency", "rows": 12},
                "timestamp": TS,
            },
            admin, endorsers, TS,
        )
