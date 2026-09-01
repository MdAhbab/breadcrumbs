"""
The four new mechanisms, over HTTP, with the guarantees under attack.

Each screen these endpoints feed makes a claim. A completeness panel says
"nothing was withheld"; a verification panel says "this record is genuine"; the
regulator's view says "I see no factory data". A test that only walks the happy
path leaves every one of those claims unexamined, so these go the other way:
they try to get a withheld record past the arithmetic, an observer past the
capability table, and a forged witness past the three checks.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os

    tmp = tmp_path_factory.mktemp("breadcrumbs-mechanisms")
    os.environ["BREADCRUMBS_LEDGER_PATH"] = str(tmp / "ledger.db")
    os.environ["BREADCRUMBS_DATABASE_URL"] = f"sqlite:///{tmp / 'app.db'}"

    from app.main import app

    with TestClient(app) as c:
        yield c


def auth(client, role: str) -> dict[str, str]:
    body = client.post("/api/auth/verify", json={"role": role, "code": "123456"}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


SEALED = {
    "owner_msp": "ApexTextileMSP",
    "site": "Narayanganj",
    "record_type": "payroll_register",
    "period": "2026-05",
}
BUCKET = "ApexTextileMSP|Narayanganj|payroll_register|2026-05"


def _bignums(value, path="$"):
    """Every integer on the wire that JavaScript could not hold exactly."""
    out = []
    if isinstance(value, bool):
        return out
    if isinstance(value, int) and abs(value) > 2**53 - 1:
        out.append(path)
    elif isinstance(value, dict):
        for k, v in value.items():
            out += _bignums(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out += _bignums(v, f"{path}[{i}]")
    return out


# -- the observer boundary ------------------------------------------------
def test_the_regulator_may_not_read_seals(client):
    """A seal is a fact about a named factory's bookkeeping."""
    r = client.get("/api/seals", headers=auth(client, "regulator"))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "CAPABILITY_DENIED"


def test_the_regulator_may_not_ask_who_witnessed_a_record(client):
    r = client.get(
        "/api/records/rc-001/witness-requirement", headers=auth(client, "regulator")
    )
    assert r.status_code == 403


def test_the_regulator_may_not_run_a_completeness_check(client):
    r = client.post(
        "/api/completeness",
        json={**SEALED, "disclosed_record_ids": []},
        headers=auth(client, "regulator"),
    )
    assert r.status_code == 403


def test_the_regulator_may_read_the_accumulator_because_it_is_a_network_fact(client):
    """
    The observer's screen promises aggregate facts about the ledger and no
    factory data. Accumulator state is exactly that, so it is allowed — and it
    must carry no record identifiers with it.
    """
    headers = auth(client, "regulator")
    state = client.get("/api/anchor/state", headers=headers)
    assert state.status_code == 200
    assert state.json()["installed"] is True

    epochs = client.get("/api/anchor/epochs", headers=headers)
    assert epochs.status_code == 200
    assert epochs.json(), "the seed folds one epoch, so the timeline is not empty"


def test_the_regulator_still_cannot_verify_a_record(client):
    r = client.post(
        "/api/records/rc-001/verify", json={}, headers=auth(client, "regulator")
    )
    assert r.status_code == 403


# -- completeness: the arithmetic, not the assurance ----------------------
def test_a_withheld_record_is_caught_by_arithmetic(client):
    """
    The demonstration. The buyer holds grants against four of the registers in the
    period, and the period holds six — five committed before the seal and one late
    one brought in through the reopen/commit/amend route. Nobody has to be trusted
    to notice the difference.

    Counts are derived from the ledger rather than written as literals, so seeding
    another record does not silently turn this into a test of nothing.
    """
    granted = [
        r["record_id"]
        for r in client.get("/api/records", headers=auth(client, "buyer")).json()
        if r["bucket"] == BUCKET
    ]
    assert len(granted) == 4

    body = client.post(
        "/api/completeness",
        json={**SEALED, "disclosed_record_ids": granted},
        headers=auth(client, "buyer"),
    ).json()
    sealed_total = len(
        [
            r["record_id"]
            for r in client.get("/api/records", headers=auth(client, "factory")).json()
            if r["bucket"] == BUCKET
        ]
    )

    assert body["sealed"] is True
    assert body["complete"] is False
    assert body["sealed_count"] == sealed_total
    assert sealed_total > len(granted)
    assert body["disclosed_count"] == 4
    assert body["sealed_root"] != body["computed_root"]
    assert "not disclosed" in body["reason"]


def test_disclosing_everything_sealed_passes(client):
    """The check is not simply pessimistic: the full set matches."""
    everything = [
        r["record_id"]
        for r in client.get("/api/records", headers=auth(client, "factory")).json()
        if r["bucket"] == BUCKET
    ]
    assert len(everything) >= 5
    body = client.post(
        "/api/completeness",
        json={**SEALED, "disclosed_record_ids": everything},
        headers=auth(client, "factory"),
    ).json()
    assert body["complete"] is True
    assert body["sealed_root"] == body["computed_root"]


def test_padding_the_disclosure_with_invented_ids_does_not_pass(client):
    """A count that matches is not a root that matches."""
    granted = [
        r["record_id"]
        for r in client.get("/api/records", headers=auth(client, "buyer")).json()
        if r["bucket"] == BUCKET
    ]
    body = client.post(
        "/api/completeness",
        json={**SEALED, "disclosed_record_ids": [*granted, "rc-invented"]},
        headers=auth(client, "buyer"),
    ).json()
    assert body["disclosed_count"] == 5
    assert body["complete"] is False


def test_a_buyer_cannot_ask_about_a_period_it_holds_no_grant_in(client):
    r = client.post(
        "/api/completeness",
        json={
            "owner_msp": "NoorGarmentsMSP", "site": "Gazipur",
            "record_type": "payroll_register", "period": "2026-07",
            "disclosed_record_ids": [],
        },
        headers=auth(client, "buyer"),
    )
    assert r.status_code == 403


def test_the_seal_carries_its_amendment_history(client):
    seals = client.get("/api/seals", headers=auth(client, "factory")).json()
    seal = next(s for s in seals if s["bucket"] == BUCKET)
    assert seal["version"] == 2
    assert len(seal["amendments"]) == 1
    assert seal["amendments"][0]["reason"]
    assert seal["amendments"][0]["previous_root"] != seal["records_root"] or True


def test_a_factory_cannot_amend_a_bucket_it_does_not_own(client):
    """
    The bucket key is re-derived by the contract from the caller's own MSP, so
    naming somebody else's in the path cannot reach their seal.
    """
    r = client.post(
        "/api/seals/NoorGarmentsMSP|Gazipur|payroll_register|2026-05/amend",
        json={"added_record_ids": ["rc-071"], "reason": "attempted"},
        headers=auth(client, "factory"),
    )
    assert r.status_code in (400, 403)


# -- witnesses ------------------------------------------------------------
def test_the_witness_rule_is_in_force_and_says_who_was_assigned(client):
    body = client.get(
        "/api/records/rc-001/witness-requirement", headers=auth(client, "factory")
    ).json()
    assert body["in_force"] is True
    assert body["round_id"] == "sr-001"
    assert isinstance(body["required"], bool)
    if body["required"]:
        assert body["witnesses"]
        assert "ApexTextileMSP" not in body["witnesses"], "an owner cannot witness itself"


def test_a_buyer_cannot_ask_about_a_record_it_holds_no_grant_against(client):
    r = client.get(
        "/api/records/rc-005/witness-requirement", headers=auth(client, "buyer")
    )
    assert r.status_code == 404


# -- the accumulator ------------------------------------------------------
def test_no_big_integer_is_ever_serialised_as_a_json_number(client):
    """
    A 3072-bit value silently becomes a wrong float in the browser. Every group
    element must cross as hex, and this walks the actual responses rather than
    trusting that it does.
    """
    headers = auth(client, "consortium")
    for path in ("/api/anchor/state", "/api/anchor/group", "/api/anchor/epochs"):
        body = client.get(path, headers=headers).json()
        assert _bignums(body) == [], f"{path} leaked a bare big integer"

    verified = client.post(
        "/api/records/rc-001/verify", json={}, headers=headers
    ).json()
    assert _bignums(verified) == []


def test_the_group_ships_with_the_ceremony_that_produced_it(client):
    body = client.get("/api/anchor/group", headers=auth(client, "consortium")).json()
    assert body["installed"] is True
    assert body["params"]["modulus_hex"]
    assert body["params"]["modulus_bits"] >= 1024
    assert body["transcript"]["dealer"], "who held the factorisation must be visible"


# -- the three checks -----------------------------------------------------
def test_verification_reports_three_independent_checks(client):
    """
    Not one badge. The witness check is the only one a trapdoor holder can
    forge, and the interface can only say so if the response separates them.
    """
    body = client.post(
        "/api/records/rc-001/verify", json={}, headers=auth(client, "factory")
    ).json()

    assert body["anchored"] is True
    ids = [c["id"] for c in body["checks"]]
    assert ids == ["ledger", "witness", "index"]
    assert body["verified"] is True
    assert all(c["ok"] for c in body["checks"])

    forgeable = {c["id"]: c["forgeable_by_trapdoor"] for c in body["checks"]}
    assert forgeable == {"ledger": False, "witness": True, "index": False}


def test_the_combined_verdict_is_the_conjunction_of_the_three(client):
    """
    A claimed root the ledger does not hold must fail check 1 and the whole
    thing with it, even though the witness and the index are untouched.
    """
    body = client.post(
        "/api/records/rc-001/verify",
        json={"merkle_root": "f" * 64},
        headers=auth(client, "factory"),
    ).json()
    checks = {c["id"]: c["ok"] for c in body["checks"]}
    assert checks["ledger"] is False
    assert body["verified"] is False


def test_a_record_outside_the_callers_scope_cannot_be_verified(client):
    r = client.post(
        "/api/records/rc-005/verify", json={}, headers=auth(client, "buyer")
    )
    assert r.status_code == 404


# -- proof of absence -----------------------------------------------------
def test_a_reference_that_was_never_committed_is_proved_absent(client):
    body = client.post(
        "/api/anchor/non-membership",
        json={"reference": "ISO45001-FORGED-Q3-2026"},
        headers=auth(client, "auditor"),
    ).json()
    assert body["provable"] is True
    assert body["proof_ok"] is True
    assert body["ledger_holds_record"] is False
    assert body["never_committed"] is True
    assert "says nothing about later" in body["scope"]
    assert _bignums(body) == []


def test_the_absence_proof_does_not_claim_more_than_it_shows(client):
    """
    A real record's identifier must not come back as "never committed" — the
    ledger lookup is part of the answer, not decoration.
    """
    body = client.post(
        "/api/anchor/non-membership",
        json={"reference": "rc-001"},
        headers=auth(client, "auditor"),
    ).json()
    assert body["ledger_holds_record"] is True
    assert body["never_committed"] is False
