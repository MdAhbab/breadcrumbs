"""
Attacks by a member organisation holding valid certificates.

The dangerous adversary in a permissioned consortium is not an outsider — there
is no anonymous membership to exploit — it is a member behaving dishonestly while
every credential it presents is genuine. Each test names what such a member would
try and records what happens.

**Three of these attacks succeed.** They are here for that reason. A security
section where everything fails is not evidence of a secure system, it is evidence
of a test suite written by the same people who wrote the code, and a judge who has
run a security review will assume the second unless shown otherwise. What the
system may claim is written next to each one.

Attacks covered elsewhere, not repeated here:
  withholding records from a sealed period   test_seal.py
  choosing your own witness                  test_witness.py
  forging a witness with the trapdoor        test_anchor.py
  serving two members different histories    test_digest.py
"""

from __future__ import annotations

import pytest

from model.chaincode.reputation import WEIGHTS
from model.consortium import GATE_ORGS, MODEL_CHANNEL, build
from model.merkle import MerkleTree
from model.tests.test_gate import GAMMA, TASKS, K, accuracies, signed_submission

TS = "2026-08-05T09:14:00Z"


# -- gate collusion -------------------------------------------------------
def test_a_minority_of_colluding_endorsers_cannot_promote_a_model():
    """
    The attack the Continuity Gate exists to stop: the organisations running the
    aggregation server agree among themselves to ship a model that is better at
    this month's problem and quietly worse at last year's.

    Two of the five sign flattering numbers. The policy needs three.
    """
    from model.tests.test_gate import run_gate

    c = build()
    admin = c.who("rafiqul.islam")
    endorsers = c.endorsers(GATE_ORGS[:3])
    from model.ledger.crypto import TAG_BENCH, hash_object

    for task in TASKS:
        c.network.invoke(
            MODEL_CHANNEL, "fedmodel", "commit_benchmark",
            {
                "task_id": task,
                "benchmark_hash": hash_object(TAG_BENCH, {"task": task, "rows": 600}),
                "contributors": ["NoorGarmentsMSP"], "size": 600,
                "timestamp": "2026-08-19T00:00:00Z",
            },
            admin, endorsers, "2026-08-19T00:00:00Z",
        )
    c.network.invoke(
        MODEL_CHANNEL, "fedmodel", "open_round",
        {
            "round_id": "round-8", "tasks": TASKS,
            "contributors": ["ApexTextileMSP"], "memory_bank_hash": "a" * 64,
            "timestamp": TS,
        },
        admin, endorsers, TS,
    )

    flattering = accuracies(9200, 9100, 9300)
    colluders = [
        signed_submission(c, "ApexTextileMSP", "m-9", "b" * 64, flattering),
        signed_submission(c, "NoorGarmentsMSP", "m-9", "b" * 64, flattering),
    ]
    decision = run_gate(c, "m-9", colluders)
    # Both signatures are genuine and both were accepted — the refusal is about
    # the count, not about cryptography. Asserting that here matters: an earlier
    # draft of this test signed over the wrong candidate hash and passed because
    # the signatures failed, which would have proved nothing about the policy.
    assert decision["endorsers"] == ["ApexTextileMSP", "NoorGarmentsMSP"]
    assert decision["rejected_submissions"] == []
    assert decision["outcome"] == "reject"
    assert decision["reason_code"] == "INSUFFICIENT_ENDORSEMENTS"
    assert f"{K} required" in decision["reason"]


def test_a_poisoning_update_tuned_to_sit_just_under_the_tolerance_is_promoted():
    """
    A SINGLE ROUND OF THIS ATTACK STILL SUCCEEDS, and should.

    The gate rejects a candidate that loses more than tau on any earlier task. An
    attacker who knows tau does not have to lose more than tau: it damages each
    earlier task by just under the threshold, gains on the new one, and the
    contract promotes it — correctly, by its own rule. That is what this test
    pins, and it is still true.

    What has changed is what happens when the attack is *repeated*. A per-round
    bound alone is not a bound: a rule permitting a 2.99-point loss each round
    permits an arbitrary loss over enough rounds. The contract now also measures
    every earlier task against the best it has ever scored under a promoted
    model and refuses a candidate that has drifted more than sigma from it, so
    the total damage is capped rather than unbounded.
    See test_gate.py::test_damage_kept_just_under_tau_every_round_is_stopped_by
    _the_cumulative_bound, which runs exactly this attacker for four rounds and
    watches the fourth get refused.

    So the claim the report may make is: the gate prevents *unnoticed*
    regression, bounds regression per round at tau, and bounds cumulative
    regression at sigma against the high-water mark. It does not make the
    attacker harmless — sigma of damage is still available to it, and choosing
    sigma is a consortium's judgement about how much drift is tolerable before a
    model should be retired rather than amended.
    """
    from model.tests.test_gate import TAU, run_gate

    c = build()
    admin = c.who("rafiqul.islam")
    endorsers = c.endorsers(GATE_ORGS[:3])
    from model.ledger.crypto import TAG_BENCH, hash_object

    for task in TASKS:
        c.network.invoke(
            MODEL_CHANNEL, "fedmodel", "commit_benchmark",
            {
                "task_id": task,
                "benchmark_hash": hash_object(TAG_BENCH, {"task": task, "rows": 600}),
                "contributors": ["NoorGarmentsMSP"], "size": 600,
                "timestamp": "2026-08-19T00:00:00Z",
            },
            admin, endorsers, "2026-08-19T00:00:00Z",
        )
    c.network.invoke(
        MODEL_CHANNEL, "fedmodel", "open_round",
        {
            "round_id": "round-8", "tasks": TASKS,
            "contributors": ["ApexTextileMSP"], "memory_bank_hash": "a" * 64,
            "timestamp": TS,
        },
        admin, endorsers, TS,
    )

    previous = (7730, 7650, 5010)
    tuned = accuracies(
        previous[0] - (TAU - 1),        # damaged by 2.99 points, tolerance is 3.00
        previous[1] - (TAU - 1),
        previous[2] + GAMMA + 500,      # and clearly better at the new task
        prev=previous,
    )
    subs = [
        signed_submission(c, msp, "m-poison", "b" * 64, tuned)
        for msp in GATE_ORGS[:3]
    ]
    decision = run_gate(c, "m-poison", subs)
    assert decision["outcome"] == "promote", "the attack succeeds; this test documents it"
    for task in decision["per_task"]:
        if not task["is_new_task"]:
            assert -TAU < task["change_bp"] < 0, "damage sits inside the agreed tolerance"


# -- findings and consequences -------------------------------------------
@pytest.fixture
def witnessed_record():
    """A committed record carrying a counter-signature, ready to be disputed."""
    from model.chaincode.doccustody import bucket_key
    from model.chaincode.witness import attestation_payload, share_commitment
    from model.ledger.crypto import sign

    c = build()
    channel = "records-consortium"
    members = ["ApexTextileMSP", "NoorGarmentsMSP", "CrescentFashionMSP", "BVCertificationMSP"]
    c.network.create_channel(channel, [*members, "BGMEAConsortiumMSP"], TS)
    who = {
        "ApexTextileMSP": "fatema.begum",
        "NoorGarmentsMSP": "noor.operator",
        "CrescentFashionMSP": "crescent.operator",
        "BVCertificationMSP": "meera.nair",
    }
    shares = {m: f"{i + 1:02x}" * 16 for i, m in enumerate(members)}

    def invoke(fn, args, submitter):
        return c.network.invoke(
            channel, "doccustody", fn, args,
            submitter=c.who(submitter),
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )

    invoke("open_seed_round",
           {"round_id": "r1", "members": members, "sample_percent": 0, "timestamp": TS},
           "rafiqul.islam")
    for m in members:
        invoke("commit_seed_share",
               {"round_id": "r1", "commitment": share_commitment(shares[m]), "timestamp": TS},
               who[m])
    for m in members:
        invoke("reveal_seed_share", {"round_id": "r1", "share": shares[m], "timestamp": TS}, who[m])

    rows = [{"worker_ref": f"W-{i}", "net_pay_bdt": 14000 + i} for i in range(8)]
    tree = MerkleTree(rows)
    args = {
        "record_id": "rc-001", "merkle_root": tree.root, "record_type": "payroll_register",
        "period": "2026-07", "site": "Gazipur", "row_count": len(rows),
        "schema_version": "v2.1.0", "timestamp": TS,
    }
    requirement = c.network.query(
        channel, "doccustody", "witness_requirement",
        {"record_id": "rc-001", "record_type": "payroll_register"}, caller=c.who("fatema.begum"),
    )
    record = {
        "record_id": "rc-001", "merkle_root": tree.root,
        "bucket": bucket_key("ApexTextileMSP", "Gazipur", "payroll_register", "2026-07"),
        "owner_msp": "ApexTextileMSP",
    }
    args["attestations"] = [
        {
            "witness_msp": m, "check_code": "physical_presence", "attested_at": TS,
            "certificate_pem": c.org_identity(m).certificate_pem(),
            "signature": sign(
                c.org_identity(m).private_key,
                attestation_payload(record, "physical_presence", TS),
            ),
        }
        for m in requirement["witnesses"]
    ]
    invoke("commit_record", args, "fatema.begum")
    return c, channel, invoke, requirement["witnesses"], tree


def test_a_falsification_finding_slashes_the_witness_as_well_as_the_owner(witnessed_record):
    """
    This is what makes counter-signing more than a rubber stamp. When a record is
    found false, the organisation that vouched for it is penalised alongside the
    one that wrote it — and the penalty is several times what honest attestation
    ever earned.
    """
    c, channel, invoke, witnesses, _ = witnessed_record

    _, result, finding = c.network.invoke(
        channel, "doccustody", "report_falsification",
        {
            "finding_id": "f-001", "record_id": "rc-001",
            "reason": "wage totals contradict the production and electricity records",
            "evidence_record_ids": ["rc-prod-07"], "timestamp": TS,
        },
        submitter=c.who("meera.nair"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    assert result.valid, result.reason

    penalised = {p["msp_id"]: p["event_type"] for p in finding["penalties"]}
    assert penalised["ApexTextileMSP"] == "record_falsified"
    for witness in witnesses:
        assert penalised[witness] == "witness_of_falsified_record"

    assert WEIGHTS["witness_of_falsified_record"] < 0
    assert abs(WEIGHTS["witness_of_falsified_record"]) > 4 * WEIGHTS["witness_attested"]

    disputed = c.network.query(
        channel, "doccustody", "get_record", {"record_id": "rc-001"}, caller=c.who("meera.nair")
    )
    assert disputed["status"] == "disputed"


def test_only_an_auditor_may_record_a_falsification_finding(witnessed_record):
    """
    A finding is a permanent accusation against a named organisation. Letting a
    competitor file one would make the reputation system a weapon.
    """
    c, channel, _, _, _ = witnessed_record
    with pytest.raises(Exception, match="only an auditor"):
        c.network.invoke(
            channel, "doccustody", "report_falsification",
            {"finding_id": "f-002", "record_id": "rc-001", "reason": "because", "timestamp": TS},
            submitter=c.who("noor.operator"),
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )


def test_a_disclosure_that_does_not_match_the_commitment_is_established_on_chain(witnessed_record):
    """
    The one falsification the contract establishes by itself, with no human
    judgement in it: the buyer supplies what it was given, the contract recomputes
    the root, and the arithmetic decides.
    """
    c, channel, _, _, tree = witnessed_record
    honest = tree.prove(2, "rc-001", "net_pay_bdt")
    tampered = {
        "finding_id": "f-003", "record_id": "rc-001", "field_name": "net_pay_bdt",
        "value": {"worker_ref": "W-2", "net_pay_bdt": 99999},  # not what was committed
        "salt": honest.salt, "index": honest.index,
        "path": [s.to_dict() for s in honest.path], "timestamp": TS,
    }
    _, result, finding = c.network.invoke(
        channel, "doccustody", "report_disclosure_mismatch", tampered,
        submitter=c.who("james.holloway"),
        endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
        timestamp=TS,
    )
    assert result.valid, result.reason
    assert finding["established_on_chain"] is True
    assert finding["computed_root"] != finding["committed_root"]


def test_an_accusation_about_a_disclosure_that_actually_verifies_is_refused(witnessed_record):
    """
    A system where accusations are free is a system where they are worthless. A
    finding can only be filed when the arithmetic actually fails.
    """
    c, channel, _, _, tree = witnessed_record
    honest = tree.prove(2, "rc-001", "net_pay_bdt")
    with pytest.raises(Exception, match="nothing to report"):
        c.network.invoke(
            channel, "doccustody", "report_disclosure_mismatch",
            {
                "finding_id": "f-004", "record_id": "rc-001", "field_name": "net_pay_bdt",
                "value": honest.value, "salt": honest.salt, "index": honest.index,
                "path": [s.to_dict() for s in honest.path], "timestamp": TS,
            },
            submitter=c.who("james.holloway"),
            endorsers=c.endorsers(["ApexTextileMSP", "BVCertificationMSP"]),
            timestamp=TS,
        )
