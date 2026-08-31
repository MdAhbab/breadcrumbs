"""
Tests for the ledger's security properties.

Each test names a specific way the system could be cheated and shows it is
caught. A passing suite here is the evidence behind "no single participant can
decide", which is otherwise just a claim in a slide deck.
"""

from __future__ import annotations

import pytest

from model.consortium import DOCUMENT_CHANNEL, MODEL_CHANNEL, build
from model.ledger import AND, NOutOf, OR, SignedBy
from model.ledger.block import Endorsement
from model.ledger.crypto import public_bytes, sign
from model.ledger.identity import CertificateAuthority, MSP
from model.merkle import MerkleTree, verify_disclosure

TS = "2026-08-05T09:14:00Z"


@pytest.fixture
def consortium():
    return build()


@pytest.fixture
def committed(consortium):
    """A consortium with one payroll register already committed."""
    rows = [{"worker_id": f"APX-{4400 + i}", "net_pay_bdt": 14000 + i * 7} for i in range(1847)]
    tree = MerkleTree(rows)
    consortium.network.invoke(
        DOCUMENT_CHANNEL,
        "doccustody",
        "commit_record",
        {
            "record_id": "rc-001",
            "merkle_root": tree.root,
            "record_type": "payroll_register",
            "period": "2026-07",
            "site": "Gazipur",
            "row_count": 1847,
            "schema_version": "v2.1.0",
            "timestamp": TS,
        },
        submitter=consortium.who("fatema.begum"),
        endorsers=consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    return consortium, tree


# -- identity -------------------------------------------------------------
def test_rogue_ca_claiming_a_real_msp_id_is_rejected(consortium):
    """
    The attack: generate your own CA, name it ApexTextileMSP, issue yourself an
    admin certificate. Checking only the MSP ID string would accept it.
    """
    rogue_ca = CertificateAuthority("ApexTextileMSP", "Not Apex", "factory")
    imposter = rogue_ca.issue("imposter", "admin")
    ok, reason = consortium.msp.validate(imposter)
    assert not ok
    assert "not issued by this organisation's CA" in reason


def test_revoked_certificate_is_rejected(consortium):
    ident = consortium.who("fatema.begum")
    assert consortium.msp.validate(ident)[0]
    consortium.authorities["ApexTextileMSP"].revoke(ident)
    ok, reason = consortium.msp.validate(ident)
    assert not ok and "revoked" in reason


def test_role_comes_from_the_certificate_not_the_claim(consortium):
    assert consortium.msp.role_of(consortium.who("fatema.begum")) == "operator"
    assert consortium.msp.role_of(consortium.who("rafiqul.islam")) == "admin"
    assert consortium.msp.role_of(consortium.who("aziz")) == "reader"


# -- endorsement policy ---------------------------------------------------
def test_policy_counts_organisations_not_signatures(consortium):
    """
    The attack: one factory signs five times with five employee certificates to
    satisfy a 3-of-5 policy. Deduplicating by MSP ID is what stops it.
    """
    policy = NOutOf(3, ["ApexTextileMSP", "NoorGarmentsMSP", "BVCertificationMSP"])
    assert not policy.satisfied_by({"ApexTextileMSP"})
    assert policy.satisfied_by({"ApexTextileMSP", "NoorGarmentsMSP", "BVCertificationMSP"})


def test_policy_algebra():
    p = AND("A", OR("B", "C"))
    assert p.satisfied_by({"A", "B"})
    assert p.satisfied_by({"A", "C"})
    assert not p.satisfied_by({"B", "C"})
    assert SignedBy("A").describe() == "A"
    assert AND("A", "B").describe() == "AND(A, B)"
    assert OR("A", "B").describe() == "OR(A, B)"
    assert NOutOf(2, ["A", "B", "C"]).describe() == "2-of(A, B, C)"


def test_forged_endorsement_signature_is_rejected(committed):
    """A signature that does not verify must not contribute its organisation."""
    consortium, _ = committed
    net = consortium.network
    tx = net.propose(
        DOCUMENT_CHANNEL,
        "doccustody",
        "grant_access",
        {
            "grant_id": "g-forge",
            "record_id": "rc-001",
            "requester_msp": "PrimarkSourcingMSP",
            "purpose_code": "ETH-WAGE-VERIFY",
            "field_name": "net_pay_bdt",
            "expires_at": "2026-09-30T00:00:00Z",
            "timestamp": TS,
        },
        submitter=consortium.who("fatema.begum"),
        endorsers=consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    # Corrupt the auditor's signature.
    good = tx.endorsements[1]
    tx.endorsements[1] = Endorsement(
        good.msp_id, good.identity_id, good.public_key, "00" * 64
    )
    net.submit(tx)
    net.commit(TS)
    result = net.channels[DOCUMENT_CHANNEL].validation[tx.tx_id]
    assert not result.valid
    assert result.code == "ENDORSEMENT_POLICY_FAILURE"


def test_endorsement_by_an_outsider_does_not_satisfy_the_policy(committed):
    """An organisation not named in the policy contributes nothing."""
    consortium, _ = committed
    net = consortium.network
    tx = net.propose(
        DOCUMENT_CHANNEL,
        "doccustody",
        "grant_access",
        {
            "grant_id": "g-outsider",
            "record_id": "rc-001",
            "requester_msp": "PrimarkSourcingMSP",
            "purpose_code": "ETH-WAGE-VERIFY",
            "field_name": "net_pay_bdt",
            "expires_at": "2026-09-30T00:00:00Z",
            "timestamp": TS,
        },
        submitter=consortium.who("fatema.begum"),
        endorsers=consortium.endorsers(["ApexTextileMSP"]),
        timestamp=TS,
    )
    # Add the regulator, who is not in AND(Apex, BV).
    outsider = consortium.who("aziz")
    tx.endorsements.append(
        Endorsement(
            outsider.msp_id,
            outsider.id,
            public_bytes(outsider.public_key),
            sign(outsider.private_key, tx.payload()),
        )
    )
    net.submit(tx)
    net.commit(TS)
    assert not net.channels[DOCUMENT_CHANNEL].validation[tx.tx_id].valid


# -- chain integrity ------------------------------------------------------
def test_chain_verifies_when_untouched(committed):
    consortium, _ = committed
    ok, why = consortium.network.channels[DOCUMENT_CHANNEL].verify_chain()
    assert ok, why


def test_tampering_with_a_committed_transaction_breaks_the_chain(committed):
    """
    The attack: quietly edit a committed record's root hash. The block's data
    hash changes, so its own hash changes, so the next block's back-link fails.
    """
    consortium, _ = committed
    channel = consortium.network.channels[DOCUMENT_CHANNEL]
    assert channel.verify_chain()[0]

    victim = channel.blocks[1]
    victim.transactions[0].args["merkle_root"] = "f" * 64

    ok, why = channel.verify_chain()
    assert not ok
    assert "does not match its committed hash" in why


def test_block_numbers_must_be_contiguous(committed):
    consortium, _ = committed
    channel = consortium.network.channels[DOCUMENT_CHANNEL]
    channel.blocks[1].number = 7
    ok, why = channel.verify_chain()
    assert not ok and "claims number 7" in why


# -- MVCC -----------------------------------------------------------------
def test_stale_read_set_is_invalidated(committed):
    """
    Two transactions revoke the same grant. The second simulated against an
    older version of the key and must be rejected at validation rather than
    applied on top of the first.
    """
    consortium, _ = committed
    net = consortium.network
    grant_args = {
        "grant_id": "g-001",
        "record_id": "rc-001",
        "requester_msp": "PrimarkSourcingMSP",
        "purpose_code": "ETH-WAGE-VERIFY",
        "field_name": "net_pay_bdt",
        "expires_at": "2026-09-30T00:00:00Z",
        "timestamp": TS,
    }
    net.invoke(
        DOCUMENT_CHANNEL,
        "doccustody",
        "grant_access",
        grant_args,
        consortium.who("fatema.begum"),
        consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        TS,
    )

    endorsers = consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"])
    revoke = {"grant_id": "g-001", "reason": "scope exceeded", "timestamp": TS}
    # Both simulate against the same state before either commits.
    tx_a = net.propose(
        DOCUMENT_CHANNEL, "doccustody", "revoke_access", revoke,
        consortium.who("fatema.begum"), endorsers, TS,
    )
    tx_b = net.propose(
        DOCUMENT_CHANNEL, "doccustody", "revoke_access", dict(revoke, reason="duplicate"),
        consortium.who("fatema.begum"), endorsers, TS,
    )
    net.submit(tx_a)
    net.commit(TS)
    net.submit(tx_b)
    net.commit(TS)

    v = net.channels[DOCUMENT_CHANNEL].validation
    assert v[tx_a.tx_id].valid
    assert not v[tx_b.tx_id].valid
    assert v[tx_b.tx_id].code == "MVCC_READ_CONFLICT"


def test_invalid_transactions_stay_in_the_block(committed):
    """
    A rejected transaction is recorded, not dropped. An auditor asking "did
    anyone try this?" is entitled to an answer.
    """
    consortium, _ = committed
    net = consortium.network
    before = net.channels[DOCUMENT_CHANNEL].height
    tx = net.propose(
        DOCUMENT_CHANNEL, "doccustody", "grant_access",
        {
            "grant_id": "g-bad", "record_id": "rc-001",
            "requester_msp": "PrimarkSourcingMSP", "purpose_code": "ETH-WAGE-VERIFY",
            "field_name": "net_pay_bdt", "expires_at": "2026-09-30T00:00:00Z",
            "timestamp": TS,
        },
        consortium.who("fatema.begum"),
        consortium.endorsers(["ApexTextileMSP"]),  # policy needs BV too
        TS,
    )
    net.submit(tx)
    net.commit(TS)
    channel = net.channels[DOCUMENT_CHANNEL]
    assert channel.height == before + 1
    assert tx.tx_id in [t.tx_id for t in channel.head.transactions]
    assert not channel.validation[tx.tx_id].valid


# -- ordering -------------------------------------------------------------
def test_ordering_refuses_writes_without_a_quorum(consortium):
    """Losing a majority stops accepting writes rather than forking."""
    orderer = consortium.network.orderer
    assert orderer.quorum == 3
    orderer.stop("orderer0.bgmea")
    orderer.stop("orderer1.bgmea")
    assert orderer.has_quorum()
    orderer.stop("orderer2.apex")
    assert not orderer.has_quorum()

    block, result, _ = consortium.network.invoke(
        DOCUMENT_CHANNEL, "doccustody", "commit_record",
        {
            "record_id": "rc-noquorum", "merkle_root": "a" * 64,
            "record_type": "payroll_register", "period": "2026-08",
            "site": "Savar", "row_count": 5, "schema_version": "v2.1.0",
            "timestamp": TS,
        },
        consortium.who("fatema.begum"),
        consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        TS,
    )
    assert block is None
    assert result.code == "ORDERING_FAILURE"
    assert "no quorum" in result.reason


def test_leader_fails_over(consortium):
    orderer = consortium.network.orderer
    assert orderer.leader_id == "orderer0.bgmea"
    orderer.stop("orderer0.bgmea")
    assert orderer.leader_id == "orderer1.bgmea"
    assert orderer.term == 2


# -- access control -------------------------------------------------------
def test_a_buyer_cannot_commit_a_factorys_record(consortium):
    from model.ledger import ChaincodeError

    with pytest.raises(ChaincodeError, match="not a factory"):
        consortium.network.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_record",
            {
                "record_id": "rc-x", "merkle_root": "a" * 64,
                "record_type": "payroll_register", "period": "2026-07",
                "site": "Gazipur", "row_count": 10, "schema_version": "v2.1.0",
                "timestamp": TS,
            },
            consortium.who("james.holloway"),
            consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            TS,
        )


def test_verification_outside_the_granted_scope_is_refused(committed):
    """
    A grant covers one field. Asking about another is refused by the contract,
    not merely logged. This is the /403 screen in the designs.
    """
    from model.ledger import ChaincodeError

    consortium, _ = committed
    net = consortium.network
    net.invoke(
        DOCUMENT_CHANNEL, "doccustody", "grant_access",
        {
            "grant_id": "g-scope", "record_id": "rc-001",
            "requester_msp": "PrimarkSourcingMSP", "purpose_code": "ETH-WAGE-VERIFY",
            "field_name": "net_pay_bdt", "expires_at": "2026-09-30T00:00:00Z",
            "timestamp": TS,
        },
        consortium.who("fatema.begum"),
        consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        TS,
    )
    with pytest.raises(ChaincodeError, match="grant covers net_pay_bdt"):
        net.invoke(
            DOCUMENT_CHANNEL, "doccustody", "record_verification",
            {
                "receipt_id": "vr-x", "grant_id": "g-scope",
                "field_name": "national_id",  # not the granted field
                "result": "match", "computed_root": "a" * 64,
                "timestamp": "2026-08-22T17:04:00Z",
            },
            consortium.who("james.holloway"),
            consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            "2026-08-22T17:04:00Z",
        )


def test_expired_grant_cannot_be_used(committed):
    from model.ledger import ChaincodeError

    consortium, _ = committed
    net = consortium.network
    net.invoke(
        DOCUMENT_CHANNEL, "doccustody", "grant_access",
        {
            "grant_id": "g-exp", "record_id": "rc-001",
            "requester_msp": "PrimarkSourcingMSP", "purpose_code": "ETH-WAGE-VERIFY",
            "field_name": "net_pay_bdt", "expires_at": "2026-07-31T00:00:00Z",
            "timestamp": TS,
        },
        consortium.who("fatema.begum"),
        consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        TS,
    )
    with pytest.raises(ChaincodeError, match="expired"):
        net.invoke(
            DOCUMENT_CHANNEL, "doccustody", "record_verification",
            {
                "receipt_id": "vr-exp", "grant_id": "g-exp", "field_name": "net_pay_bdt",
                "result": "match", "computed_root": "a" * 64,
                "timestamp": "2026-08-22T17:04:00Z",
            },
            consortium.who("james.holloway"),
            consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            "2026-08-22T17:04:00Z",
        )


# -- determinism ----------------------------------------------------------
def test_nondeterministic_chaincode_is_caught_at_endorsement(consortium):
    """
    Two endorsers simulating a contract that reads a clock or a random number
    produce different write sets. That must be detected before ordering, not
    discovered later as a fork.
    """
    import random

    from model.ledger import ChaincodeError

    def flaky(ctx, function, args):
        ctx.put("k", random.random())
        return "ok"

    consortium.network.install(
        "flaky", flaky, AND("ApexTextileMSP", "BVCertificationMSP"),
        ["ApexTextileMSP", "BVCertificationMSP"],
    )
    with pytest.raises(ChaincodeError, match="not deterministic"):
        consortium.network.propose(
            MODEL_CHANNEL, "flaky", "go", {},
            consortium.who("fatema.begum"),
            consortium.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            TS,
        )
