"""
Tests for the Continuity Gate — Algorithm 1 of the report.

Every branch of the algorithm gets a test, because this contract is the project's
central claim and "we wrote it" is not the same as "it does what the paper says".

Accuracies are in basis points: 7790 means 77.90%.
"""

from __future__ import annotations

import pytest

from model.consortium import GATE_ORGS, MODEL_CHANNEL, build
from model.ledger.crypto import TAG_BENCH, hash_object, sign

TS = "2026-08-20T10:00:00Z"

TASKS = ["wage_register_inconsistency", "forged_certificate", "chemical_misreporting"]
NEW_TASK = "chemical_misreporting"

# The gate parameters the consortium agreed. gamma: a candidate must gain at
# least 2.00pp on the new task. tau: it may not lose more than 3.00pp on any
# earlier one. k: three organisations must evaluate. delta: they may differ by
# at most 1.00pp before the contract calls it a disagreement.
GAMMA, TAU, K, DELTA = 200, 300, 3, 100


def signed_submission(consortium, msp_id, candidate_id, candidate_hash, accuracies):
    """One organisation's off-chain evaluation, signed."""
    ident = consortium.org_identity(msp_id)
    payload = {
        "round_id": "round-8",
        "candidate_id": candidate_id,
        "candidate_hash": candidate_hash,
        "accuracies": accuracies,
    }
    return {
        "endorser_msp": msp_id,
        "certificate_pem": ident.certificate_pem(),
        "signature": sign(ident.private_key, payload),
        "accuracies": accuracies,
    }


def accuracies(wage, cert, chem, prev=(7730, 7650, 5010)):
    """Build an accuracy map: candidate values plus the previous model's."""
    cand = (wage, cert, chem)
    return {
        t: {"candidate_bp": cand[i], "previous_bp": prev[i]} for i, t in enumerate(TASKS)
    }


@pytest.fixture
def ready():
    """A consortium with benchmarks committed and a round open."""
    c = build()
    admin = c.who("rafiqul.islam")
    endorsers = c.endorsers(GATE_ORGS[:3])

    for task in TASKS:
        c.network.invoke(
            MODEL_CHANNEL, "fedmodel", "commit_benchmark",
            {
                "task_id": task,
                "benchmark_hash": hash_object(TAG_BENCH, {"task": task, "rows": 600}),
                "contributors": ["NoorGarmentsMSP", "CrescentFashionMSP"],
                "size": 600,
                "timestamp": "2026-08-19T00:00:00Z",
            },
            admin, endorsers, "2026-08-19T00:00:00Z",
        )

    c.network.invoke(
        MODEL_CHANNEL, "fedmodel", "open_round",
        {
            "round_id": "round-8",
            "tasks": TASKS,
            "contributors": ["ApexTextileMSP", "NoorGarmentsMSP", "CrescentFashionMSP"],
            "memory_bank_hash": "7c1d" + "0" * 56 + "9ab4",
            "timestamp": TS,
        },
        admin, endorsers, TS,
    )
    return c


def run_gate(consortium, candidate_id, subs, **overrides):
    args = {
        "round_id": "round-8",
        "candidate_id": candidate_id,
        "candidate_hash": "b" * 64,
        "parent_id": "m-v7",
        "new_task": NEW_TASK,
        "submissions": subs,
        "gamma_bp": GAMMA,
        "tau_bp": TAU,
        "k": K,
        "delta_bp": DELTA,
        "timestamp": TS,
    }
    args.update(overrides)
    _, result, response = consortium.network.invoke(
        MODEL_CHANNEL, "fedmodel", "evaluate_gate", args,
        consortium.who("rafiqul.islam"),
        consortium.endorsers(GATE_ORGS[:3]),
        TS,
    )
    assert result.valid, result.reason
    return response


# -- the happy path -------------------------------------------------------
def test_a_candidate_that_improves_everything_is_promoted(ready):
    subs = [
        signed_submission(ready, m, "m-v8-rc1", "b" * 64, accuracies(7790, 7700, 7990))
        for m in GATE_ORGS[:3]
    ]
    d = run_gate(ready, "m-v8-rc1", subs)
    assert d["outcome"] == "promote"
    assert d["reason_code"] == "OK"
    assert all(t["pass"] for t in d["per_task"])

    current = ready.network.query(
        MODEL_CHANNEL, "fedmodel", "get_current_model", {}, ready.who("rafiqul.islam")
    )
    assert current["model_id"] == "m-v8-rc1"
    assert current["status"] == "promoted"


# -- the demo's money shot ------------------------------------------------
def test_a_candidate_that_forgot_an_earlier_task_is_rejected(ready):
    """
    The whole point of the mechanism.

    This candidate is *excellent* at the new task — 79.9% on chemical
    misreporting, up from chance. A committee scoring update quality on the
    current round's data would wave it through. It has also lost 11.4 points on
    wage-register inconsistency, which the network already knew. The gate is the
    only thing looking backwards.
    """
    subs = [
        signed_submission(ready, m, "m-v8-rc2", "b" * 64, accuracies(6590, 7680, 7990))
        for m in GATE_ORGS[:3]
    ]
    d = run_gate(ready, "m-v8-rc2", subs)

    assert d["outcome"] == "reject"
    assert d["reason_code"] == "REGRESSION"
    assert "wage_register_inconsistency" in d["reason"]
    assert "1140 bp" in d["reason"]

    failing = [t for t in d["per_task"] if not t["pass"]]
    assert len(failing) == 1
    assert failing[0]["task_id"] == "wage_register_inconsistency"
    assert failing[0]["change_bp"] == -1140

    # It gained on the new task, which is exactly why a forward-looking check
    # would have missed this.
    new = [t for t in d["per_task"] if t["is_new_task"]][0]
    assert new["change_bp"] == 2980 and new["pass"]


def test_a_rejection_leaves_the_previous_model_in_force(ready):
    good = [
        signed_submission(ready, m, "m-v8-rc1", "b" * 64, accuracies(7790, 7700, 7990))
        for m in GATE_ORGS[:3]
    ]
    run_gate(ready, "m-v8-rc1", good)

    # Re-open a round for the second candidate.
    ready.network.invoke(
        MODEL_CHANNEL, "fedmodel", "open_round",
        {
            "round_id": "round-9", "tasks": TASKS,
            "contributors": ["ApexTextileMSP"], "memory_bank_hash": "a" * 64,
            "timestamp": TS,
        },
        ready.who("rafiqul.islam"), ready.endorsers(GATE_ORGS[:3]), TS,
    )
    # Signed against round-9, so the payload the endorsers signed matches.
    bad = []
    for m in GATE_ORGS[:3]:
        ident = ready.org_identity(m)
        acc = accuracies(6000, 7700, 8200, prev=(7790, 7700, 7990))
        payload = {
            "round_id": "round-9", "candidate_id": "m-v9-rc1",
            "candidate_hash": "c" * 64, "accuracies": acc,
        }
        bad.append({
            "endorser_msp": m,
            "certificate_pem": ident.certificate_pem(),
            "signature": sign(ident.private_key, payload),
            "accuracies": acc,
        })

    _, result, d = ready.network.invoke(
        MODEL_CHANNEL, "fedmodel", "evaluate_gate",
        {
            "round_id": "round-9", "candidate_id": "m-v9-rc1", "candidate_hash": "c" * 64,
            "parent_id": "m-v8-rc1", "new_task": NEW_TASK, "submissions": bad,
            "gamma_bp": GAMMA, "tau_bp": TAU, "k": K, "delta_bp": DELTA, "timestamp": TS,
        },
        ready.who("rafiqul.islam"), ready.endorsers(GATE_ORGS[:3]), TS,
    )
    assert d["outcome"] == "reject"
    current = ready.network.query(
        MODEL_CHANNEL, "fedmodel", "get_current_model", {}, ready.who("rafiqul.islam")
    )
    assert current["model_id"] == "m-v8-rc1"


# -- the other rejection branches ----------------------------------------
def test_too_few_endorsements_is_a_rejection(ready):
    subs = [
        signed_submission(ready, m, "m-v8-rc3", "b" * 64, accuracies(7790, 7700, 7990))
        for m in GATE_ORGS[:2]
    ]
    d = run_gate(ready, "m-v8-rc3", subs)
    assert d["outcome"] == "reject"
    assert d["reason_code"] == "INSUFFICIENT_ENDORSEMENTS"
    assert "2 organisations" in d["reason"]


def test_endorsers_disagreeing_beyond_delta_is_a_rejection(ready):
    """
    If two organisations evaluating the same committed benchmark get materially
    different numbers, something is wrong with the benchmark, the model or one of
    the evaluators. The contract refuses rather than picking a winner.
    """
    subs = [
        signed_submission(ready, GATE_ORGS[0], "m-v8-rc4", "b" * 64, accuracies(7790, 7700, 7990)),
        signed_submission(ready, GATE_ORGS[1], "m-v8-rc4", "b" * 64, accuracies(7795, 7700, 7990)),
        signed_submission(ready, GATE_ORGS[2], "m-v8-rc4", "b" * 64, accuracies(7000, 7700, 7990)),
    ]
    d = run_gate(ready, "m-v8-rc4", subs)
    assert d["outcome"] == "reject"
    assert d["reason_code"] == "NO_AGREEMENT"
    assert "795 bp" in d["reason"]


def test_disagreement_within_delta_is_tolerated_and_the_median_is_used(ready):
    subs = [
        signed_submission(ready, GATE_ORGS[0], "m-v8-rc5", "b" * 64, accuracies(7750, 7700, 7990)),
        signed_submission(ready, GATE_ORGS[1], "m-v8-rc5", "b" * 64, accuracies(7790, 7700, 7990)),
        signed_submission(ready, GATE_ORGS[2], "m-v8-rc5", "b" * 64, accuracies(7830, 7700, 7990)),
    ]
    d = run_gate(ready, "m-v8-rc5", subs)
    assert d["outcome"] == "promote"
    wage = [t for t in d["per_task"] if t["task_id"] == "wage_register_inconsistency"][0]
    assert wage["candidate_bp"] == 7790  # the median, not the mean or the max


def test_no_real_improvement_on_the_new_task_is_a_rejection(ready):
    """A model that changes nothing must not be promoted just for existing."""
    subs = [
        signed_submission(ready, m, "m-v8-rc6", "b" * 64, accuracies(7790, 7700, 5060))
        for m in GATE_ORGS[:3]
    ]
    d = run_gate(ready, "m-v8-rc6", subs)
    assert d["outcome"] == "reject"
    assert d["reason_code"] == "NO_IMPROVEMENT"
    assert "50 bp" in d["reason"]


def test_a_loss_within_tolerance_is_allowed(ready):
    """Tau is a tolerance, not zero. A 2.00pp dip is inside the agreed 3.00pp."""
    subs = [
        signed_submission(ready, m, "m-v8-rc7", "b" * 64, accuracies(7530, 7700, 7990))
        for m in GATE_ORGS[:3]
    ]
    d = run_gate(ready, "m-v8-rc7", subs)
    assert d["outcome"] == "promote"


# -- signature and submission integrity ----------------------------------
def test_a_forged_submission_signature_does_not_count(ready):
    subs = [
        signed_submission(ready, m, "m-v8-rc8", "b" * 64, accuracies(7790, 7700, 7990))
        for m in GATE_ORGS[:3]
    ]
    subs[2]["signature"] = "00" * 64
    d = run_gate(ready, "m-v8-rc8", subs)
    assert d["outcome"] == "reject"
    assert d["reason_code"] == "INSUFFICIENT_ENDORSEMENTS"
    assert any("signature does not verify" in r["reason"] for r in d["rejected_submissions"])


def test_tampering_with_the_accuracies_after_signing_is_caught(ready):
    """
    The attack: sign honest numbers, then edit them upward before submission.
    The signature covers the accuracies, so it stops verifying.
    """
    subs = [
        signed_submission(ready, m, "m-v8-rc9", "b" * 64, accuracies(6590, 7680, 7990))
        for m in GATE_ORGS[:3]
    ]
    subs[0]["accuracies"]["wage_register_inconsistency"]["candidate_bp"] = 7790
    d = run_gate(ready, "m-v8-rc9", subs)
    assert any("signature does not verify" in r["reason"] for r in d["rejected_submissions"])


# -- the vulnerability that defeated the whole guarantee ------------------
def test_one_actor_cannot_forge_every_organisations_evaluation(ready):
    """
    Regression test for the worst bug this project had.

    The contract used to verify each submission against a public key the
    *submission itself carried*, checking only that the organisation's name was
    known. So a single actor could generate three keypairs, label them with
    three organisations, sign whatever accuracies flattered its model, and
    promote it alone — which is precisely the thing the Continuity Gate exists to
    make impossible.

    The fix: resolve the certificate against the MSP first, and take the public
    key out of the validated certificate.
    """
    from model.ledger.crypto import generate_signing_key

    flattering = accuracies(9200, 9800, 10000, prev=(9160, 9780, 4800))
    subs = []
    for msp_id in GATE_ORGS[:3]:
        attacker_key = generate_signing_key()  # certified by nobody
        payload = {
            "round_id": "round-8", "candidate_id": "m-forged",
            "candidate_hash": "b" * 64, "accuracies": flattering,
        }
        subs.append({
            "endorser_msp": msp_id,
            "certificate_pem": "-----BEGIN CERTIFICATE-----\nnope\n-----END CERTIFICATE-----",
            "signature": sign(attacker_key, payload),
            "accuracies": flattering,
        })

    d = run_gate(ready, "m-forged", subs)
    assert d["outcome"] == "reject"
    assert d["reason_code"] == "INSUFFICIENT_ENDORSEMENTS"
    assert d["endorsers"] == []
    assert len(d["rejected_submissions"]) == 3


def test_a_real_certificate_from_the_wrong_organisation_is_rejected(ready):
    """
    Subtler variant: a genuine, validly-issued certificate, but presented as
    though it belonged to a different organisation. The subject must match the
    MSP it claims.
    """
    acc = accuracies(7790, 7700, 7990)
    impostor = ready.org_identity("PrimarkSourcingMSP")  # a real member...
    payload = {
        "round_id": "round-8", "candidate_id": "m-wrongorg",
        "candidate_hash": "b" * 64, "accuracies": acc,
    }
    subs = [
        signed_submission(ready, GATE_ORGS[0], "m-wrongorg", "b" * 64, acc),
        signed_submission(ready, GATE_ORGS[1], "m-wrongorg", "b" * 64, acc),
        {
            "endorser_msp": GATE_ORGS[2],          # ...claiming to be someone else
            "certificate_pem": impostor.certificate_pem(),
            "signature": sign(impostor.private_key, payload),
            "accuracies": acc,
        },
    ]
    d = run_gate(ready, "m-wrongorg", subs)
    assert d["outcome"] == "reject"
    assert d["reason_code"] == "INSUFFICIENT_ENDORSEMENTS"
    assert any(
        "not issued by this organisation" in r["reason"]
        or "does not belong to" in r["reason"]
        for r in d["rejected_submissions"]
    )


def test_one_organisation_cannot_submit_twice_to_reach_the_threshold(ready):
    """Three submissions, one organisation. The threshold is organisations."""
    acc = accuracies(7790, 7700, 7990)
    subs = [signed_submission(ready, GATE_ORGS[0], "m-v8-rc10", "b" * 64, acc) for _ in range(3)]
    d = run_gate(ready, "m-v8-rc10", subs)
    assert d["outcome"] == "reject"
    assert d["reason_code"] == "INSUFFICIENT_ENDORSEMENTS"
    assert sum(1 for r in d["rejected_submissions"] if r["reason"] == "duplicate submission") == 2


def test_an_endorser_that_skipped_a_task_is_not_counted(ready):
    subs = [
        signed_submission(ready, m, "m-v8-rc11", "b" * 64, accuracies(7790, 7700, 7990))
        for m in GATE_ORGS[:3]
    ]
    partial = dict(subs[2]["accuracies"])
    partial.pop("forged_certificate")
    ident = ready.org_identity(GATE_ORGS[2])
    payload = {
        "round_id": "round-8", "candidate_id": "m-v8-rc11",
        "candidate_hash": "b" * 64, "accuracies": partial,
    }
    subs[2] = {
        "endorser_msp": GATE_ORGS[2],
        "certificate_pem": ident.certificate_pem(),
        "signature": sign(ident.private_key, payload),
        "accuracies": partial,
    }
    d = run_gate(ready, "m-v8-rc11", subs)
    assert d["reason_code"] == "INSUFFICIENT_ENDORSEMENTS"
    assert any("did not evaluate" in r["reason"] for r in d["rejected_submissions"])


# -- benchmark commitment -------------------------------------------------
def test_a_round_cannot_open_without_committed_benchmarks():
    from model.ledger import ChaincodeError

    c = build()
    with pytest.raises(ChaincodeError, match="no benchmark committed"):
        c.network.invoke(
            MODEL_CHANNEL, "fedmodel", "open_round",
            {
                "round_id": "r-x", "tasks": ["never_committed"],
                "contributors": ["ApexTextileMSP"], "memory_bank_hash": "a" * 64,
                "timestamp": TS,
            },
            c.who("rafiqul.islam"), c.endorsers(GATE_ORGS[:3]), TS,
        )


def test_revealing_different_contents_than_were_committed_is_refused(ready):
    """
    Without this check the commit-reveal scheme would be theatre: a member could
    commit one benchmark and reveal a friendlier one afterwards.
    """
    from model.ledger import ChaincodeError

    with pytest.raises(ChaincodeError, match="but .* was committed"):
        ready.network.invoke(
            MODEL_CHANNEL, "fedmodel", "reveal_benchmark",
            {
                "task_id": TASKS[0],
                "contents": {"task": TASKS[0], "rows": 599},  # committed with 600
                "timestamp": TS,
            },
            ready.who("rafiqul.islam"), ready.endorsers(GATE_ORGS[:3]), TS,
        )


def test_revealing_the_committed_contents_succeeds(ready):
    r = ready.network.invoke(
        MODEL_CHANNEL, "fedmodel", "reveal_benchmark",
        {"task_id": TASKS[0], "contents": {"task": TASKS[0], "rows": 600}, "timestamp": TS},
        ready.who("rafiqul.islam"), ready.endorsers(GATE_ORGS[:3]), TS,
    )[2]
    assert r["revealed"] and r["verified"]


# -- the audit trail ------------------------------------------------------
def test_every_decision_is_recorded_with_who_evaluated_it(ready):
    subs = [
        signed_submission(ready, m, "m-v8-rc12", "b" * 64, accuracies(6590, 7680, 7990))
        for m in GATE_ORGS[:3]
    ]
    run_gate(ready, "m-v8-rc12", subs)
    d = ready.network.query(
        MODEL_CHANNEL, "fedmodel", "get_decision",
        {"candidate_id": "m-v8-rc12"}, ready.who("aziz"),
    )
    assert d["outcome"] == "reject"
    assert sorted(d["endorsers"]) == sorted(GATE_ORGS[:3])
    assert d["memory_bank_hash"].startswith("7c1d")
    assert d["parameters"] == {"gamma_bp": GAMMA, "tau_bp": TAU, "k": K, "delta_bp": DELTA}
    # Each task carries the benchmark hash it was judged against.
    assert all(len(t["benchmark_hash"]) == 64 for t in d["per_task"])


def test_the_gate_policy_requires_three_organisations():
    """
    The transaction itself needs 3-of-5 endorsements. A single organisation
    cannot invoke the gate at all, whatever numbers it holds.
    """
    c = build()
    tx_policy = c.network.chaincodes["fedmodel"].policy
    assert not tx_policy.satisfied_by({"ApexTextileMSP"})
    assert not tx_policy.satisfied_by({"ApexTextileMSP", "BGMEAConsortiumMSP"})
    assert tx_policy.satisfied_by(
        {"ApexTextileMSP", "BGMEAConsortiumMSP", "BVCertificationMSP"}
    )
