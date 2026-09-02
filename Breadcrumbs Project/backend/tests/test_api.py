"""
API tests, with authorization as the main subject.

The interesting failures in a system like this are not crashes, they are
endpoints that quietly answer a question they should have refused. The regulator
screen promises it shows no factory data; these tests are where that promise is
either true or not.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A fresh API over a throwaway ledger and store."""
    import os

    tmp = tmp_path_factory.mktemp("breadcrumbs")
    os.environ["BREADCRUMBS_LEDGER_PATH"] = str(tmp / "ledger.db")
    os.environ["BREADCRUMBS_DATABASE_URL"] = f"sqlite:///{tmp / 'app.db'}"

    # Imported after the environment is set, so settings pick the temp paths up.
    from app import world
    from app.main import app

    with TestClient(app) as c:
        # The seed runs on a background thread so the API can answer straight
        # away; a test that asks before it finishes gets a 503, correctly.
        world.wait()
        yield c


def auth(client, role: str) -> dict[str, str]:
    body = client.post("/api/auth/verify", json={"role": role, "code": "123456"}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture(scope="module")
def payroll_grant(client):
    """
    A live payroll grant, found rather than assumed.

    The world is built from the corpus now, so record identifiers are corpus
    document ids and the row counts are whatever the generator produced. These
    tests care about the *shape* of a disclosure proof — one row out, a
    logarithmic path — so they discover a subject and derive the expected path
    length from the record's own row count.
    """
    buyer = auth(client, "buyer")
    grants = [
        g for g in client.get("/api/grants", headers=buyer).json()
        if g["status"] == "active" and g["field_name"] == "net_pay_bdt"
    ]
    assert grants, "the buyer holds no live payroll grant"
    grant = grants[0]
    record = client.get(
        f"/api/records/{grant['record_id']}", headers=buyer
    ).json()["record"]
    return {"grant": grant, "record": record}



# -- authentication -------------------------------------------------------
def test_every_role_can_sign_in_and_lands_somewhere_useful(client):
    for option in client.get("/api/auth/roles").json():
        body = client.post(
            "/api/auth/verify", json={"role": option["role"], "code": "123456"}
        ).json()
        assert body["access_token"]
        assert body["landing"].startswith("/")


def test_a_code_that_is_not_six_digits_is_refused(client):
    for code in ["", "12345", "1234567", "abcdef", "12 345"]:
        r = client.post("/api/auth/verify", json={"role": "factory", "code": code})
        assert r.status_code == 400


def test_an_endpoint_requires_a_token(client):
    assert client.get("/api/records").status_code == 401


def test_a_garbage_token_is_refused(client):
    r = client.get("/api/records", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


# -- authorization: the part that was wrong -------------------------------
def test_the_regulator_cannot_read_factory_records(client):
    """
    Regression test. The regulator's own screen says it sees aggregate
    governance data only. The API used to serve it every committed record.
    """
    headers = auth(client, "regulator")
    r = client.get("/api/records", headers=headers)
    assert r.status_code == 403
    assert "may not read records" in r.json()["detail"]["message"]

    assert client.get("/api/grants", headers=headers).status_code == 403


def test_the_regulator_can_still_see_what_it_is_promised(client):
    headers = auth(client, "regulator")
    assert client.get("/api/regulator/overview", headers=headers).status_code == 200
    assert client.get("/api/ops/sla", headers=headers).status_code == 200
    assert client.get("/api/ledger/channels", headers=headers).status_code == 200


def test_the_regulator_cannot_write_anything(client):
    headers = auth(client, "regulator")
    r = client.post(
        "/api/verify", headers=headers,
        json={
            "grant_id": "g-0001", "record_id": "doc-any", "row_index": 0,
            "field_name": "net_pay_bdt", "receipt_id": "vr-reg",
        },
    )
    assert r.status_code == 403


def test_a_buyer_sees_only_records_it_holds_a_grant_against(client):
    """
    Regression test. The listing was unscoped, so any signed-in caller received
    every record on the channel regardless of what it had been granted.
    """
    buyer = client.get("/api/records", headers=auth(client, "buyer")).json()
    factory = client.get("/api/records", headers=auth(client, "factory")).json()

    assert len(buyer) < len(factory)
    granted = {
        g["record_id"]
        for g in client.get("/api/grants", headers=auth(client, "buyer")).json()
        if g["status"] == "active"
    }
    assert {r["record_id"] for r in buyer} == granted


def test_a_factory_sees_only_its_own_records(client):
    records = client.get("/api/records", headers=auth(client, "factory")).json()
    assert records
    assert {r["owner_msp"] for r in records} == {"ApexTextileMSP"}


# -- verification ---------------------------------------------------------
def test_verifying_one_row_proves_it_without_revealing_the_rest(client, payroll_grant):
    import math

    grant, record = payroll_grant["grant"], payroll_grant["record"]
    rows = record["row_count"]
    r = client.post(
        "/api/verify", headers=auth(client, "buyer"),
        json={
            "grant_id": grant["grant_id"], "record_id": grant["record_id"],
            "row_index": 0, "field_name": "net_pay_bdt", "receipt_id": "vr-t1",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verified"] is True
    assert body["proof"]["match"] is True
    assert body["proof"]["rows_disclosed"] == 1
    assert body["proof"]["rows_in_record"] == rows
    # Logarithmic, not linear. That is the entire claim, and it is asserted
    # against the record's real size rather than against a remembered constant.
    assert len(body["proof"]["steps"]) == math.ceil(math.log2(rows))


def test_verifying_a_field_outside_the_grant_is_refused_by_the_contract(client, payroll_grant):
    grant = payroll_grant["grant"]
    r = client.post(
        "/api/verify", headers=auth(client, "buyer"),
        json={
            "grant_id": grant["grant_id"], "record_id": grant["record_id"],
            "row_index": 0, "field_name": "national_id", "receipt_id": "vr-t2",
        },
    )
    assert r.status_code == 403
    # The chaincode's own sentence, not a generic failure.
    assert "grant covers net_pay_bdt" in r.json()["detail"]["message"]


def test_a_record_that_does_not_exist_is_a_404(client, payroll_grant):
    r = client.post(
        "/api/verify", headers=auth(client, "buyer"),
        json={
            "grant_id": payroll_grant["grant"]["grant_id"], "record_id": "doc-nope",
            "row_index": 0, "field_name": "net_pay_bdt", "receipt_id": "vr-t3",
        },
    )
    assert r.status_code == 404


def test_a_row_index_past_the_end_is_rejected(client, payroll_grant):
    grant = payroll_grant["grant"]
    r = client.post(
        "/api/verify", headers=auth(client, "buyer"),
        json={
            "grant_id": grant["grant_id"], "record_id": grant["record_id"],
            "row_index": 999_999, "field_name": "net_pay_bdt", "receipt_id": "vr-t4",
        },
    )
    assert r.status_code == 400


# -- the ledger -----------------------------------------------------------
def test_the_chain_verifies_through_the_api(client):
    body = client.get("/api/ledger/verify", headers=auth(client, "factory")).json()
    assert body["ok"] is True
    assert all(c["integrity_ok"] for c in body["channels"])


def test_blocks_are_listed_per_channel(client):
    headers = auth(client, "factory")
    channels = client.get("/api/ledger/channels", headers=headers).json()
    for channel in channels:
        blocks = client.get(
            f"/api/ledger/blocks?channel={channel['channel']}", headers=headers
        ).json()
        assert blocks
        # A block belongs to exactly one channel.
        for block in blocks:
            assert block["transaction_count"] == len(block["transactions"])


def test_health_reports_ledger_integrity(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["ledger_integrity"] is True
    assert "invented" in body["note"]
