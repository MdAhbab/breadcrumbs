"""
Asking for several columns at once, and admitting a member for real.

Both of these were shapes the product described and did not have. A buyer could
only ask for one column per request, so checking whether a wage was correct
meant sending four unrelated requests; and a membership motion could reach its
threshold, go green, and leave the organisation it admitted existing nowhere.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("breadcrumbs-multi")
    os.environ["BREADCRUMBS_LEDGER_PATH"] = str(tmp / "ledger.db")
    os.environ["BREADCRUMBS_DATABASE_URL"] = f"sqlite:///{tmp / 'app.db'}"

    from app import world
    from app.main import app

    with TestClient(app) as c:
        world.wait()
        yield c


def auth(client, role: str) -> dict[str, str]:
    body = client.post("/api/auth/verify", json={"role": role, "code": "123456"}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


# ------------------------------------------------ asking for several things --

def ask(client, fields: list[str], period: str = "2027-05"):
    return client.post(
        "/api/requests", headers=auth(client, "buyer"),
        json={
            "supplier_msp": "ApexTextileMSP", "record_type": "payroll_register",
            "period": period, "purpose_code": "ETH-WAGE-VERIFY",
            "field_names": fields, "expires_at": "2028-12-31T00:00:00Z",
        },
    )


def test_one_ask_can_name_several_columns(client):
    r = ask(client, ["basic_bdt", "ot_pay_bdt", "deductions_bdt"])
    assert r.status_code == 201
    body = r.json()
    assert len(body["ids"]) == 3
    # Grouped, so the factory sees one ask rather than three unrelated rows.
    assert body["batch_id"]

    rows = client.get("/api/requests", headers=auth(client, "buyer")).json()
    mine = [x for x in rows if x["id"] in body["ids"]]
    assert {x["field_name"] for x in mine} == {"basic_bdt", "ot_pay_bdt", "deductions_bdt"}
    assert {x["batch_id"] for x in mine} == {body["batch_id"]}
    # Each is still its own request, because a grant covers exactly one column.
    assert all(x["status"] == "pending" for x in mine)


def test_a_single_column_ask_is_not_forced_into_a_batch(client):
    body = ask(client, ["grade"]).json()
    assert len(body["ids"]) == 1
    assert body["batch_id"] is None


def test_asking_again_for_something_still_outstanding_is_refused(client):
    ask(client, ["ot_hours"], period="2027-06")
    again = ask(client, ["ot_hours"], period="2027-06")
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "ALREADY_ASKED"


def test_a_repeat_ask_still_carries_the_columns_that_are_new(client):
    ask(client, ["days_worked"], period="2027-07")
    both = ask(client, ["days_worked", "attendance_bonus_bdt"], period="2027-07")
    assert both.status_code == 201
    body = both.json()
    assert body["skipped"] == ["days_worked"]
    assert len(body["ids"]) == 1


def test_the_factory_can_answer_a_whole_batch_at_once(client):
    factory = auth(client, "factory")
    record = next(
        r for r in client.get("/api/records", headers=factory).json()
        if r["record_type"] == "payroll_register"
    )
    ids = ask(client, ["basic_bdt", "ot_rate_bdt"], period="2027-08").json()["ids"]

    r = client.post(
        "/api/requests/grant-batch", headers=factory,
        json={"request_ids": ids, "record_id": record["record_id"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["granted"]) == 2, body
    assert not body["failed"]

    # Two grants, one per column. The narrowness is the guarantee and a batch
    # answer must not quietly widen it.
    grants = client.get("/api/grants", headers=auth(client, "buyer")).json()
    issued = {g["grant_id"]: g for g in grants}
    for entry in body["granted"]:
        assert issued[entry["grant_id"]]["record_id"] == record["record_id"]
    assert {issued[e["grant_id"]]["field_name"] for e in body["granted"]} == {
        "basic_bdt", "ot_rate_bdt"
    }


def test_a_batch_reports_the_ones_it_could_not_release(client):
    """Not atomic on purpose: what was released stays released."""
    factory = auth(client, "factory")
    record = next(
        r for r in client.get("/api/records", headers=factory).json()
        if r["record_type"] == "payroll_register"
    )
    ids = ask(client, ["net_pay_bdt"], period="2027-09").json()["ids"]
    r = client.post(
        "/api/requests/grant-batch", headers=factory,
        json={"request_ids": [*ids, "br-does-not-exist"], "record_id": record["record_id"]},
    )
    body = r.json()
    assert len(body["granted"]) == 1
    assert len(body["failed"]) == 1
    assert body["failed"][0]["request_id"] == "br-does-not-exist"


# ------------------------------------------------------- membership is real --

def test_a_carried_admission_puts_the_member_on_the_ledger(client):
    consortium = auth(client, "consortium")
    before = client.get("/api/orgs", headers=consortium).json()
    assert not any(o["msp_id"] == "DeltaKnitwearMSP" for o in before)

    # p-001 needs three and ships with two, so this endorsement carries it.
    r = client.post("/api/governance/proposals/p-001/endorse", headers=consortium)
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["status"] == "approved"
    assert body["executed_tx"], "the motion carried but nothing was written"

    after = client.get("/api/orgs", headers=consortium).json()
    admitted = next(o for o in after if o["msp_id"] == "DeltaKnitwearMSP")
    assert admitted["kind"] == "factory"
    assert admitted["admitted_by_proposal"] == "p-001"
    # Admitted to the consortium is not the same as party to a document, and the
    # directory should not blur the two.
    assert admitted["channels"] == []
    assert admitted["on_document_channel"] is False


def test_the_register_says_who_admitted_a_member_and_why(client):
    members = client.get(
        "/api/governance/members", headers=auth(client, "consortium")
    ).json()
    delta = next(m for m in members if m["msp_id"] == "DeltaKnitwearMSP")
    assert delta["status"] == "active"
    assert delta["founding"] is False
    assert delta["proposal_id"] == "p-001"

    founder = next(m for m in members if m["msp_id"] == "ApexTextileMSP")
    assert founder["founding"] is True
    assert founder["proposal_id"] is None


def test_admitting_the_same_member_twice_is_refused_by_the_contract(client):
    """The execution guard, and the chaincode behind it, both hold."""
    consortium = auth(client, "consortium")
    again = client.post("/api/governance/proposals/p-001/endorse", headers=consortium)
    assert again.status_code == 409


def test_the_regulator_sees_the_new_member_in_its_totals(client):
    """An observer that cannot see a membership change is not observing."""
    overview = client.get(
        "/api/regulator/overview", headers=auth(client, "regulator")
    ).json()
    assert overview["kpis"]["active_factories"] == 4
    assert overview["kpis"]["total_organisations"] == 8
