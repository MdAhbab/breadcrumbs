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


def test_a_buyer_cannot_read_a_record_it_holds_no_grant_against(client):
    """
    Regression test, and the hole this rule had for a while.

    The listing was scoped, `/screen` was scoped, `/witness-requirement` and
    `/verify` were both scoped and each had a test named after the rule — and
    `GET /api/records/{id}` served any record on the channel to any signed-in
    caller that knew an identifier. A URL typed by hand is exactly how somebody
    would find that.

    404 rather than 403 on purpose: "you may not see this record" and "there is
    no such record" have to be indistinguishable, or the refusal confirms the
    document exists.
    """
    buyer = auth(client, "buyer")
    granted = {r["record_id"] for r in client.get("/api/records", headers=buyer).json()}
    everything = client.get("/api/records", headers=auth(client, "factory")).json()
    outside = next(r["record_id"] for r in everything if r["record_id"] not in granted)

    assert client.get(f"/api/records/{outside}", headers=buyer).status_code == 404
    # And the ones it does hold are still readable.
    held = next(iter(granted))
    assert client.get(f"/api/records/{held}", headers=buyer).status_code == 200


# -- the request a buyer makes, and the factory's side of it --------------
def test_a_request_carries_the_live_state_of_the_grant_that_answered_it(client):
    """
    A grant is revoked through an endpoint that has never heard of the request
    row, so a stored status went stale the moment access was withdrawn — and the
    screen it went stale on was the buyer's, about its own access. `grant_status`
    is read off the chain on every call.
    """
    buyer, factory = auth(client, "buyer"), auth(client, "factory")
    made = client.post(
        "/api/requests", headers=buyer,
        json={
            "supplier_msp": "ApexTextileMSP", "record_type": "chemical_inventory",
            "period": "2026-07", "purpose_code": "REACH-COMPLIANCE",
            "field_name": "cas_number", "expires_at": "2028-12-31T00:00:00Z",
        },
    )
    assert made.status_code == 201
    request_id = made.json()["id"]

    def row() -> dict:
        return next(
            r for r in client.get("/api/requests", headers=buyer).json()
            if r["id"] == request_id
        )

    assert row()["status"] == "pending"
    assert row()["grant_status"] is None

    record = next(
        r for r in client.get("/api/records", headers=factory).json()
        if r["record_type"] == "chemical_inventory" and r["period"] == "2026-07"
    )
    answered = client.post(
        f"/api/requests/{request_id}/grant", headers=factory,
        json={"record_id": record["record_id"]},
    )
    assert answered.status_code == 200
    grant_id = answered.json()["grant_id"]
    assert answered.json()["reissued"] is False
    assert row()["grant_status"] == "active"

    # A second grant on a live one is a duplicate, not a recovery.
    again = client.post(
        f"/api/requests/{request_id}/grant", headers=factory,
        json={"record_id": record["record_id"]},
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "GRANT_IS_LIVE"

    revoked = client.post(
        f"/api/grants/{grant_id}/revoke?reason=audit+window+closed", headers=factory
    )
    assert revoked.status_code == 200
    assert row()["status"] == "granted"
    assert row()["grant_status"] == "revoked"
    assert row()["grant_revoked_reason"] == "audit window closed"

    # And now access can be issued again — as a new grant, not as the old one
    # coming back. The revoked one stays exactly where it is.
    reissued = client.post(
        f"/api/requests/{request_id}/grant", headers=factory,
        json={"record_id": record["record_id"]},
    )
    assert reissued.status_code == 200
    assert reissued.json()["reissued"] is True
    assert reissued.json()["grant_id"] != grant_id
    grants = {g["grant_id"]: g for g in client.get("/api/grants", headers=factory).json()}
    assert grants[grant_id]["status"] == "revoked"
    assert grants[reissued.json()["grant_id"]]["status"] == "active"


def test_a_declined_request_can_be_reconsidered(client):
    """A decline used to be terminal, so one misclick ended a buyer's request."""
    buyer, factory = auth(client, "buyer"), auth(client, "factory")
    request_id = client.post(
        "/api/requests", headers=buyer,
        json={
            "supplier_msp": "ApexTextileMSP", "record_type": "safety_inspection",
            "period": "2026-05", "purpose_code": "ETH-SAFETY",
            "field_name": "finding_code", "expires_at": "2028-12-31T00:00:00Z",
        },
    ).json()["id"]

    declined = client.post(
        f"/api/requests/{request_id}/decline", headers=factory,
        json={"reason": "this period is still open"},
    )
    assert declined.status_code == 200
    assert declined.json()["reason"] == "this period is still open"

    def row() -> dict:
        return next(
            r for r in client.get("/api/requests", headers=buyer).json()
            if r["id"] == request_id
        )

    assert row()["status"] == "declined"
    assert row()["decline_reason"] == "this period is still open"

    # Granting a declined request tells you to reopen it rather than silently
    # answering a decision that was already made.
    refused = client.post(
        f"/api/requests/{request_id}/grant", headers=factory, json={"record_id": "doc-any"}
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "REQUEST_DECLINED"

    assert client.post(f"/api/requests/{request_id}/reconsider", headers=factory).status_code == 200
    assert row()["status"] == "pending"
    assert row()["decline_reason"] is None


def test_a_factory_can_disclose_a_record_it_left_out_of_a_period(client):
    """
    The loop the completeness check exists to close.

    A period is sealed at 40 and the buyer holds 39, so its check fails on
    arithmetic. The factory discloses the fortieth directly — there is no
    request to answer, which is why `POST /api/grants` has to work without one —
    and the same check passes, with the two roots converging. The seal never
    moves, which is the whole point: it fixed the count before any of this.
    """
    factory, buyer = auth(client, "factory"), auth(client, "buyer")
    seals = client.get("/api/seals", headers=factory).json()
    records = client.get("/api/records", headers=factory).json()
    grants = client.get("/api/grants", headers=factory).json()

    # A period the buyer is short in, found rather than hardcoded.
    def held_by_buyer(bucket: str) -> set[str]:
        return {
            g["record_id"] for g in grants
            if g["status"] == "active" and g["requester_msp"] == "PrimarkSourcingMSP"
            and any(r["record_id"] == g["record_id"] and r["bucket"] == bucket for r in records)
        }

    target = None
    for seal in seals:
        in_bucket = {r["record_id"] for r in records if r["bucket"] == seal["bucket"]}
        missing = in_bucket - held_by_buyer(seal["bucket"])
        if in_bucket and missing and len(missing) < len(in_bucket):
            target = (seal, sorted(missing)[0])
            break
    assert target, "no sealed period has a record the buyer was not given"
    seal, withheld = target

    def check() -> dict:
        mine = [
            r["record_id"] for r in client.get("/api/records", headers=buyer).json()
            if r["bucket"] == seal["bucket"]
        ]
        return client.post(
            "/api/completeness", headers=buyer,
            json={
                "owner_msp": seal["owner_msp"], "site": seal["site"],
                "record_type": seal["record_type"], "period": seal["period"],
                "disclosed_record_ids": mine,
            },
        ).json()

    before = check()
    assert before["complete"] is False
    assert before["sealed_root"] != before["computed_root"]

    sibling = next(
        g for g in grants
        if g["status"] == "active" and g["requester_msp"] == "PrimarkSourcingMSP"
        and any(r["record_id"] == g["record_id"] and r["bucket"] == seal["bucket"] for r in records)
    )
    # No grant_id: the API mints one rather than making the caller invent a
    # unique ledger key and discover the collision from the contract.
    written = client.post(
        "/api/grants", headers=factory,
        json={
            "record_id": withheld, "requester_msp": sibling["requester_msp"],
            "purpose_code": sibling["purpose_code"], "field_name": sibling["field_name"],
            "expires_at": sibling["expires_at"],
        },
    )
    assert written.status_code == 201, written.text
    assert written.json()["response"]["grant_id"].startswith("g-")

    after = check()
    assert after["complete"] is True
    assert after["sealed_count"] == after["disclosed_count"]
    assert after["sealed_root"] == after["computed_root"]
    # The seal did not move. It could not: it was fixed before any of this.
    assert after["sealed_count"] == before["sealed_count"]

    # Put the world back. The period this found is the corpus's withholding
    # attack, which later tests in this suite assert the shape of, and the app
    # module is imported once so they share the ledger this fixture built.
    # Revoking is also the other half of the claim: access follows the grant, so
    # withdrawing it returns the check to exactly the shortfall it started at.
    revoked = client.post(
        f"/api/grants/{written.json()['response']['grant_id']}/revoke"
        "?reason=restoring+the+corpus+scenario",
        headers=factory,
    )
    assert revoked.status_code == 200
    restored = check()
    assert restored["complete"] is False
    assert restored["disclosed_count"] == before["disclosed_count"]
    assert restored["computed_root"] == before["computed_root"]


def test_an_organisation_off_the_document_channel_cannot_be_a_party_to_one(client):
    """
    Every consortium member is on the model channel, so the contract's check —
    is this a known MSP — passes for organisations that cannot read a document.
    A grant to one of those was accepted, written, and unusable forever.

    The directory says which is which, so the interface can stop offering them
    and the API can stop accepting them.
    """
    factory, buyer = auth(client, "factory"), auth(client, "buyer")
    orgs = client.get("/api/orgs", headers=factory).json()
    outsider = next(o for o in orgs if not o["on_document_channel"])
    assert "documents" not in " ".join(outsider["channels"])

    record = client.get("/api/records", headers=factory).json()[0]["record_id"]
    refused = client.post(
        "/api/grants", headers=factory,
        json={
            "record_id": record, "requester_msp": outsider["msp_id"],
            "purpose_code": "X-TEST", "field_name": "cas_number",
            "expires_at": "2028-12-31T00:00:00Z",
        },
    )
    assert refused.status_code == 400
    assert refused.json()["detail"]["code"] == "NOT_ON_CHANNEL"

    # And the same rule from the other end: a buyer cannot address a request to
    # a supplier that could never answer it.
    if outsider["kind"] == "factory":
        asked = client.post(
            "/api/requests", headers=buyer,
            json={
                "supplier_msp": outsider["msp_id"], "record_type": "payroll_register",
                "period": "2027-02", "purpose_code": "ETH-WAGE-VERIFY",
                "field_name": "net_pay_bdt", "expires_at": "2028-12-31T00:00:00Z",
            },
        )
        assert asked.status_code == 400
        assert asked.json()["detail"]["code"] == "NOT_ON_CHANNEL"


def test_a_revocation_must_say_why(client):
    """The reason goes on the ledger and is shown to the party it cuts off."""
    factory = auth(client, "factory")
    live = next(
        g for g in client.get("/api/grants", headers=factory).json()
        if g["status"] == "active"
    )
    blank = client.post(f"/api/grants/{live['grant_id']}/revoke?reason=+", headers=factory)
    assert blank.status_code == 400
    assert blank.json()["detail"]["code"] == "NO_REASON"


def test_the_factory_is_told_when_a_buyer_asks(client):
    """
    The seed ships a notification for this and nothing wrote one at runtime, so
    the single event in this system that needs a person to act was the one event
    nobody was told about.
    """
    before = len(client.get("/api/notifications", headers=auth(client, "factory")).json())
    client.post(
        "/api/requests", headers=auth(client, "buyer"),
        json={
            "supplier_msp": "ApexTextileMSP", "record_type": "payroll_register",
            "period": "2027-02", "purpose_code": "ETH-WAGE-VERIFY",
            "field_name": "net_pay_bdt", "expires_at": "2028-12-31T00:00:00Z",
        },
    )
    after = client.get("/api/notifications", headers=auth(client, "factory")).json()
    assert len(after) == before + 1
    assert any(n["kind"] == "access_request" and "net_pay_bdt" in n["body"] for n in after)


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
