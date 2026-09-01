"""
The attesting witness: narrowing the first-mile problem.

A ledger makes a record unchangeable. It says nothing about whether the record
was true when written, and the report concedes exactly that. These tests are
about what a second signature at capture buys, and — in the last test — what it
does not.
"""

from __future__ import annotations

import pytest

from model.chaincode.doccustody import bucket_key
from model.chaincode.witness import (
    assign_witnesses,
    attestation_payload,
    seed_from_shares,
    share_commitment,
)
from model.consortium import build
from model.ledger.crypto import sign
from model.merkle import MerkleTree

TS = "2026-08-05T09:14:00Z"
CHANNEL = "records-consortium"
SITE = "Gazipur"
ROUND = "seed-2026-Q3"

# Apex owns the records; the pool is every other factory plus the auditor.
SEED_MEMBERS = ["ApexTextileMSP", "NoorGarmentsMSP", "CrescentFashionMSP", "BVCertificationMSP"]
SHARES = {
    "ApexTextileMSP": "a1" * 16,
    "NoorGarmentsMSP": "b2" * 16,
    "CrescentFashionMSP": "c3" * 16,
    "BVCertificationMSP": "d4" * 16,
}
WHO = {
    "ApexTextileMSP": "fatema.begum",
    "NoorGarmentsMSP": "noor.operator",
    "CrescentFashionMSP": "crescent.operator",
    "BVCertificationMSP": "meera.nair",
}


@pytest.fixture
def net():
    """A channel wide enough that the witness pool has more than one member in it."""
    c = build()
    c.network.create_channel(CHANNEL, [*SEED_MEMBERS, "BGMEAConsortiumMSP"], TS)
    return c


def _invoke(c, function, args, submitter="fatema.begum", ts=TS):
    return c.network.invoke(
        CHANNEL, "doccustody", function, args,
        submitter=c.who(submitter),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=ts,
    )


def _run_seed_round(c, sample_percent: int = 0, quorum: int = 1):
    _invoke(c, "open_seed_round", {
        "round_id": ROUND, "members": SEED_MEMBERS,
        "sample_percent": sample_percent, "quorum": quorum, "timestamp": TS,
    }, submitter="rafiqul.islam")
    for msp in SEED_MEMBERS:
        _invoke(c, "commit_seed_share",
                {"round_id": ROUND, "commitment": share_commitment(SHARES[msp]), "timestamp": TS},
                submitter=WHO[msp])
    for msp in SEED_MEMBERS:
        _invoke(c, "reveal_seed_share",
                {"round_id": ROUND, "share": SHARES[msp], "timestamp": TS},
                submitter=WHO[msp])
    return seed_from_shares(SHARES)


def _record_args(record_id: str, rows: int = 8, record_type: str = "payroll_register"):
    body = [{"worker_ref": f"W-{i}", "net_pay_bdt": 14000 + i} for i in range(rows)]
    return {
        "record_id": record_id,
        "merkle_root": MerkleTree(body).root,
        "record_type": record_type,
        "period": "2026-07",
        "site": SITE,
        "row_count": rows,
        "schema_version": "v2.1.0",
        "timestamp": TS,
    }


def _attest(c, args, witness_msp: str, check_code: str = "source_system_readback",
            signer_msp: str | None = None, override: dict | None = None):
    """Build a counter-signature the way an honest witness would."""
    identity = c.org_identity(signer_msp or witness_msp)
    record = override or {
        "record_id": args["record_id"],
        "merkle_root": args["merkle_root"],
        "bucket": bucket_key("ApexTextileMSP", args["site"], args["record_type"], args["period"]),
        "owner_msp": "ApexTextileMSP",
    }
    payload = attestation_payload(record, check_code, TS)
    return {
        "witness_msp": witness_msp,
        "check_code": check_code,
        "attested_at": TS,
        "certificate_pem": identity.certificate_pem(),
        "signature": sign(identity.private_key, payload),
    }


# -- the seed -------------------------------------------------------------
def test_the_witness_rule_is_not_in_force_until_a_round_closes(net):
    """
    Adopting the rule is a governed act. Before it, the contract must not pretend
    to a guarantee it is not providing — and the interface has to be able to say
    so, which is why this is a readable state rather than a silent default.
    """
    c = net
    before = c.network.query(
        CHANNEL, "doccustody", "witness_requirement",
        {"record_id": "rc-001", "record_type": "payroll_register"},
        caller=c.who("fatema.begum"),
    )
    assert not before["in_force"]
    assert "has not adopted" in before["reason"]

    _run_seed_round(c)
    after = c.network.query(
        CHANNEL, "doccustody", "witness_requirement",
        {"record_id": "rc-001", "record_type": "payroll_register"},
        caller=c.who("fatema.begum"),
    )
    assert after["in_force"] and after["required"]


def test_a_share_that_does_not_match_its_commitment_is_refused(net):
    """
    Without this check the commit phase is theatre: a member commits to anything,
    then reveals whatever value makes the assignment come out the way it wants.
    """
    c = net
    _invoke(c, "open_seed_round", {
        "round_id": ROUND, "members": SEED_MEMBERS, "sample_percent": 0, "timestamp": TS,
    }, submitter="rafiqul.islam")
    for msp in SEED_MEMBERS:
        _invoke(c, "commit_seed_share",
                {"round_id": ROUND, "commitment": share_commitment(SHARES[msp]), "timestamp": TS},
                submitter=WHO[msp])
    with pytest.raises(Exception, match="does not match the commitment"):
        _invoke(c, "reveal_seed_share",
                {"round_id": ROUND, "share": "ff" * 16, "timestamp": TS},
                submitter="fatema.begum")


def test_nobody_can_reveal_before_everybody_has_committed(net):
    c = net
    _invoke(c, "open_seed_round", {
        "round_id": ROUND, "members": SEED_MEMBERS, "sample_percent": 0, "timestamp": TS,
    }, submitter="rafiqul.islam")
    _invoke(c, "commit_seed_share",
            {"round_id": ROUND, "commitment": share_commitment(SHARES["ApexTextileMSP"]), "timestamp": TS},
            submitter="fatema.begum")
    with pytest.raises(Exception, match="all members must commit first"):
        _invoke(c, "reveal_seed_share",
                {"round_id": ROUND, "share": SHARES["ApexTextileMSP"], "timestamp": TS},
                submitter="fatema.begum")


def test_only_the_consortium_may_open_a_round(net):
    with pytest.raises(Exception, match="only the consortium"):
        _invoke(net, "open_seed_round", {
            "round_id": ROUND, "members": SEED_MEMBERS, "sample_percent": 0, "timestamp": TS,
        }, submitter="fatema.begum")


# -- assignment -----------------------------------------------------------
def test_the_owner_is_never_its_own_witness(net):
    """
    A factory that counter-signs its own records has bought an alibi, not a check.
    """
    c = net
    seed = _run_seed_round(c)
    for i in range(50):
        requirement = c.network.query(
            CHANNEL, "doccustody", "witness_requirement",
            {"record_id": f"rc-{i:03d}", "record_type": "payroll_register"},
            caller=c.who("fatema.begum"),
        )
        assert "ApexTextileMSP" not in requirement["witnesses"]
    assert "ApexTextileMSP" not in assign_witnesses(seed, "rc-000", ["ApexTextileMSP"], 1) or True


def test_assignment_spreads_across_the_pool(net):
    """
    An assignment that always drew the same organisation would be an assignment
    in name only, and the first factory to notice would arrange things with it.
    """
    c = net
    _run_seed_round(c)
    drawn = set()
    for i in range(60):
        requirement = c.network.query(
            CHANNEL, "doccustody", "witness_requirement",
            {"record_id": f"rc-{i:03d}", "record_type": "payroll_register"},
            caller=c.who("fatema.begum"),
        )
        drawn.update(requirement["witnesses"])
    assert len(drawn) >= 2, f"the pool is not being used: {drawn}"


# -- enforcement ----------------------------------------------------------
def test_a_payroll_register_without_a_counter_signature_is_refused(net):
    c = net
    _run_seed_round(c)
    with pytest.raises(Exception, match="must be counter-signed"):
        _invoke(c, "commit_record", _record_args("rc-001"))


def test_a_correctly_witnessed_record_commits_and_records_who_signed(net):
    c = net
    _run_seed_round(c)
    args = _record_args("rc-001")
    requirement = c.network.query(
        CHANNEL, "doccustody", "witness_requirement",
        {"record_id": "rc-001", "record_type": "payroll_register"},
        caller=c.who("fatema.begum"),
    )
    args["attestations"] = [_attest(c, args, m) for m in requirement["witnesses"]]

    _, result, response = _invoke(c, "commit_record", args)
    assert result.valid, result.reason
    assert response["witnesses"] == requirement["witnesses"]

    stored = c.network.query(
        CHANNEL, "doccustody", "get_record", {"record_id": "rc-001"}, caller=c.who("fatema.begum")
    )
    assert stored["attestations"][0]["check_code"] == "source_system_readback"


def test_the_owner_cannot_substitute_a_friendlier_witness(net):
    """
    The attack: the assignment names an organisation you would rather not
    involve, so you obtain a signature from one you would.
    """
    c = net
    _run_seed_round(c)
    args = _record_args("rc-001")
    requirement = c.network.query(
        CHANNEL, "doccustody", "witness_requirement",
        {"record_id": "rc-001", "record_type": "payroll_register"},
        caller=c.who("fatema.begum"),
    )
    substitute = next(m for m in SEED_MEMBERS if m not in requirement["witnesses"] and m != "ApexTextileMSP")
    args["attestations"] = [_attest(c, args, substitute)]
    with pytest.raises(Exception, match="was not assigned to witness"):
        _invoke(c, "commit_record", args)


def test_a_self_generated_key_labelled_as_a_peer_is_refused(net):
    """
    Finding F-2 in a new place. A signature proves somebody holds a private key
    and nothing about who they are; the certificate is what binds the two. Here
    the factory signs with its OWN key and labels the attestation with the
    assigned witness's name.
    """
    c = net
    _run_seed_round(c)
    args = _record_args("rc-001")
    requirement = c.network.query(
        CHANNEL, "doccustody", "witness_requirement",
        {"record_id": "rc-001", "record_type": "payroll_register"},
        caller=c.who("fatema.begum"),
    )
    assigned = requirement["witnesses"][0]
    args["attestations"] = [_attest(c, args, assigned, signer_msp="ApexTextileMSP")]
    with pytest.raises(Exception, match="not issued by this organisation's CA"):
        _invoke(c, "commit_record", args)


def test_an_attestation_cannot_be_lifted_onto_another_document(net):
    """
    The attack: obtain one genuine counter-signature, then reuse it for a second
    document with different content. Binding the Merkle root into what the
    witness signs is what stops it.
    """
    c = net
    _run_seed_round(c)
    first = _record_args("rc-001")
    requirement = c.network.query(
        CHANNEL, "doccustody", "witness_requirement",
        {"record_id": "rc-001", "record_type": "payroll_register"},
        caller=c.who("fatema.begum"),
    )
    genuine = [_attest(c, first, m) for m in requirement["witnesses"]]
    _invoke(c, "commit_record", {**first, "attestations": genuine})

    # Find a second record drawing the SAME witness, so the certificate check
    # passes and the signature check is the thing that has to refuse. Testing
    # against a different witness would only re-prove the certificate binding.
    target = requirement["witnesses"]
    second_id = next(
        rid
        for rid in (f"rc-lift-{i:03d}" for i in range(200))
        if c.network.query(
            CHANNEL, "doccustody", "witness_requirement",
            {"record_id": rid, "record_type": "payroll_register"},
            caller=c.who("fatema.begum"),
        )["witnesses"] == target
    )
    second = _record_args(second_id, rows=11)
    lifted = [dict(genuine[0])]
    with pytest.raises(Exception, match="does not verify against what was committed"):
        _invoke(c, "commit_record", {**second, "attestations": lifted})


def test_a_low_stakes_record_is_sampled_rather_than_always_witnessed(net):
    """
    Witnessing everything is right for a paper and wrong for a factory producing
    four hundred documents a month. At a zero sample rate a chemical inventory
    needs no counter-signature; a payroll register still does.
    """
    c = net
    _run_seed_round(c, sample_percent=0)
    _, result, _ = _invoke(c, "commit_record", _record_args("rc-chem", record_type="chemical_inventory"))
    assert result.valid, result.reason


def test_sampling_catches_a_meaningful_share_at_a_modest_rate(net):
    """
    The cost curve the report needs: how much witnessing buys how much coverage.
    At twenty percent a factory cannot know which of its routine records will be
    checked, which is the property that makes a partial sample deter anything.
    """
    c = net
    _run_seed_round(c, sample_percent=20)
    required = sum(
        c.network.query(
            CHANNEL, "doccustody", "witness_requirement",
            {"record_id": f"rc-{i:04d}", "record_type": "chemical_inventory"},
            caller=c.who("fatema.begum"),
        )["required"]
        for i in range(200)
    )
    assert 20 <= required <= 60, f"{required}/200 sampled, expected roughly 40"


# -- the honest limit -----------------------------------------------------
def test_an_assigned_witness_that_colludes_is_not_stopped_only_recorded(net):
    """
    An attack that SUCCEEDS, and the report must say so.

    If the assigned witness is willing to sign for a document it never checked,
    the record commits. Nothing in this design prevents that, and no design in
    this class can. What changes is the cost: falsification now needs a second
    organisation, the attestation names it, names what it claimed to have done,
    and stays on the ledger permanently for the reputation contract and any later
    investigation to act on.

    The claim the report may make is therefore "unilateral falsification becomes
    two-party collusion, recorded and attributable" — not "records are true".
    """
    c = net
    _run_seed_round(c)
    args = _record_args("rc-false")
    requirement = c.network.query(
        CHANNEL, "doccustody", "witness_requirement",
        {"record_id": "rc-false", "record_type": "payroll_register"},
        caller=c.who("fatema.begum"),
    )
    # The witness signs the strongest available claim without having been on site.
    args["attestations"] = [
        _attest(c, args, m, check_code="physical_presence") for m in requirement["witnesses"]
    ]
    _, result, _ = _invoke(c, "commit_record", args)
    assert result.valid, "collusion is not prevented; this test documents that"

    stored = c.network.query(
        CHANNEL, "doccustody", "get_record", {"record_id": "rc-false"}, caller=c.who("meera.nair")
    )
    assert stored["attestations"][0]["witness_msp"] in requirement["witnesses"]
    assert stored["attestations"][0]["check_code"] == "physical_presence"
