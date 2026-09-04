"""
Confirming a review of one document.

The product had a batch attestation — an auditor's statement over everything it
examined in a sitting, naming no document — and nothing at all for the question
a factory is actually asked: has anybody independent looked at *this* register,
and who. These tests are about the individual confirmation that fills that gap,
and about the two rules that stop it becoming decoration:

  * it is minted once per reviewer per document, because the same organisation
    signing the same document twice is one claim with a later date on it;
  * it can only be signed by somebody who could open the document, and only by
    a role whose job is reading documents rather than writing them.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("breadcrumbs-reviews")
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


def a_record(client, role: str) -> str:
    records = client.get("/api/records", headers=auth(client, role)).json()
    assert records, f"the {role} can see no records to review"
    return records[0]["record_id"]


def an_unconfirmed_record(client, role: str) -> str:
    """
    One this role has not already confirmed.

    The client is module-scoped, so tests share a world and an earlier one may
    have signed the first document in the list. A test about what a statement
    may say should not fail because of what an earlier test signed.
    """
    headers = auth(client, role)
    for record in client.get("/api/records", headers=headers).json():
        seen = client.get(
            f"/api/records/{record['record_id']}/reviews", headers=headers
        ).json()
        if seen["yours"] is None:
            return record["record_id"]
    pytest.skip(f"the {role} has confirmed every document it can see")


# ------------------------------------------------------------- generating one --

def test_an_auditor_generates_a_confirmation_for_an_unreviewed_document(client):
    auditor = auth(client, "auditor")
    record_id = a_record(client, "auditor")

    before = client.get(f"/api/records/{record_id}/reviews", headers=auditor).json()
    assert before["yours"] is None
    assert before["may_confirm"] is True
    # The name that will sign is the one the API resolved from the token, not
    # one the client supplied.
    assert before["you"]["name"] == "Dr. Meera Nair"

    made = client.post(
        f"/api/records/{record_id}/reviews",
        headers=auditor,
        json={"outcome": "accepted", "statement": "Register examined in full; no findings."},
    )
    assert made.status_code == 201
    body = made.json()
    assert body["id"].startswith("rv-")
    assert body["record_id"] == record_id
    assert body["reviewer_name"] == "Dr. Meera Nair"
    assert body["reviewer_role"] == "auditor"
    # A confirmation is a complete document: it carries the root it was signed
    # against, so a reader can follow it back to the chain unaided.
    assert body["merkle_root"]

    after = client.get(f"/api/records/{record_id}/reviews", headers=auditor).json()
    assert after["yours"]["id"] == body["id"]
    assert after["reviewed_before"] is True


def test_the_same_reviewer_cannot_confirm_the_same_document_twice(client):
    auditor = auth(client, "auditor")
    record_id = a_record(client, "auditor")

    client.post(
        f"/api/records/{record_id}/reviews", headers=auditor,
        json={"outcome": "accepted", "statement": "Examined and accepted."},
    )
    again = client.post(
        f"/api/records/{record_id}/reviews", headers=auditor,
        json={"outcome": "accepted", "statement": "Examined and accepted, again."},
    )
    assert again.status_code == 409
    detail = again.json()["detail"]
    assert detail["code"] == "ALREADY_REVIEWED"
    # And it says which one already stands, so the interface can show it rather
    # than leaving the reader with a refusal and nothing to look at.
    assert detail["review_id"].startswith("rv-")


def test_a_second_reviewer_gets_their_own_confirmation(client):
    """Two organisations agreeing is a fact worth being able to show."""
    record_id = a_record(client, "buyer")

    client.post(
        f"/api/records/{record_id}/reviews", headers=auth(client, "buyer"),
        json={"outcome": "accepted", "statement": "Figures released to us reconcile."},
    )
    client.post(
        f"/api/records/{record_id}/reviews", headers=auth(client, "auditor"),
        json={"outcome": "qualified", "statement": "Examined; one entry queried."},
    )

    seen = client.get(
        f"/api/records/{record_id}/reviews", headers=auth(client, "auditor")
    ).json()
    signatories = {r["reviewer_msp"] for r in seen["reviews"]}
    assert {"PrimarkSourcingMSP", "BVCertificationMSP"} <= signatories


# ------------------------------------------------------------------ the rules --

def test_the_owner_of_a_document_does_not_confirm_a_review_of_it(client):
    """
    A signature saying the paperwork was checked is worth nothing when it is the
    same organisation that wrote the paperwork.
    """
    factory = auth(client, "factory")
    record_id = a_record(client, "factory")

    refused = client.post(
        f"/api/records/{record_id}/reviews", headers=factory,
        json={"outcome": "accepted", "statement": "Our own register, checked by us."},
    )
    assert refused.status_code == 403

    # It can still see who has confirmed its documents, which is the half of
    # this a factory actually needs.
    seen = client.get(f"/api/records/{record_id}/reviews", headers=factory)
    assert seen.status_code == 200
    assert seen.json()["may_confirm"] is False


def test_a_short_finding_is_still_a_finding(client):
    """
    The rule is "say something", and it used to be twelve characters — which is
    not a rule anybody would state out loud. "it is good" is a complete finding
    and is ten characters, so the sign button sat disabled while the box plainly
    had writing in it, and said only "write what you concluded first".
    """
    buyer = auth(client, "buyer")
    record_id = an_unconfirmed_record(client, "buyer")

    made = client.post(
        f"/api/records/{record_id}/reviews", headers=buyer,
        json={"outcome": "accepted", "statement": "it is good"},
    )
    assert made.status_code == 201, made.json()


def test_a_statement_of_one_word_is_refused_with_the_rule_in_it(client):
    auditor = auth(client, "auditor")
    record_id = a_record(client, "auditor")

    refused = client.post(
        f"/api/records/{record_id}/reviews", headers=auditor,
        json={"outcome": "accepted", "statement": "fine"},
    )
    assert refused.status_code == 400
    detail = refused.json()["detail"]
    assert detail["code"] == "NO_STATEMENT"
    # The refusal names the rule rather than restating that there is one.
    assert "3 words" in detail["message"]


def test_whether_a_check_is_available_is_reported_with_the_reviews(client):
    """
    An auditor reads every document and can prove only what has been released to
    it, so most documents it opens carry no check at all. The panel needs to know
    which it is looking at: "you have not checked any row yet" is the screen
    blaming the reader for its own rule when there is no check on the page.
    """
    auditor = auth(client, "auditor")
    held = {
        g["record_id"]
        for g in client.get("/api/grants", headers=auditor).json()
        if g["status"] == "active"
    }
    everything = [r["record_id"] for r in client.get("/api/records", headers=auditor).json()]

    with_grant = next((r for r in everything if r in held), None)
    without = next((r for r in everything if r not in held), None)

    if with_grant:
        body = client.get(f"/api/records/{with_grant}/reviews", headers=auditor).json()
        assert body["may_check"] is True
    if without:
        body = client.get(f"/api/records/{without}/reviews", headers=auditor).json()
        assert body["may_check"] is False
        # And it can still be confirmed. Reading it is real access.
        assert body["may_confirm"] is True


def test_a_document_you_cannot_open_cannot_be_confirmed_or_asked_about(client):
    """
    404, not 403, and for the same reason as everywhere else: "you may not see
    this" and "there is no such record" have to be indistinguishable, or the
    refusal itself confirms the document exists.
    """
    buyer = auth(client, "buyer")
    everything = client.get("/api/records", headers=auth(client, "auditor")).json()
    visible = {
        r["record_id"] for r in client.get("/api/records", headers=buyer).json()
    }
    hidden = next(r["record_id"] for r in everything if r["record_id"] not in visible)

    assert client.get(f"/api/records/{hidden}/reviews", headers=buyer).status_code == 404
    made = client.post(
        f"/api/records/{hidden}/reviews", headers=buyer,
        json={"outcome": "accepted", "statement": "Nothing to say about it."},
    )
    assert made.status_code == 404


def test_a_confirmation_lists_the_receipts_it_rests_on(client):
    """
    The evidence is copied into the confirmation at signing time, because the
    document has to be followable back to the chain on its own.
    """
    auditor = auth(client, "auditor")
    queue = client.get("/api/audit/queue", headers=auditor).json()
    item = next((i for i in queue["items"] if i["state"] in ("queued", "passed")), None)
    if item is None:
        pytest.skip("this auditor holds no live grant to check")

    client.post(
        "/api/verify", headers=auditor,
        json={
            "grant_id": item["grant_id"], "record_id": item["record_id"],
            "row_index": 0, "field_name": item["field_name"],
            "receipt_id": f"vr-review-{item['grant_id']}",
        },
    )
    made = client.post(
        f"/api/records/{item['record_id']}/reviews", headers=auditor,
        json={"outcome": "accepted", "statement": "Checked one row and read the rest."},
    )
    # Another test may already have confirmed this document; either way what
    # matters is the confirmation that stands, so read it back.
    standing = client.get(
        f"/api/records/{item['record_id']}/reviews", headers=auditor
    ).json()["yours"]
    assert made.status_code in (201, 409)
    assert standing is not None
    assert any(c for c in standing["checks_cited"])


def test_reviews_are_scoped_to_the_parties_of_the_document(client):
    """A reviewer sees what it signed; a factory sees what was signed about it."""
    record_id = a_record(client, "buyer")
    client.post(
        f"/api/records/{record_id}/reviews", headers=auth(client, "buyer"),
        json={"outcome": "accepted", "statement": "Reconciled against the invoice."},
    )

    buyer_side = client.get("/api/reviews", headers=auth(client, "buyer")).json()
    assert buyer_side
    assert all(r["reviewer_msp"] == "PrimarkSourcingMSP" for r in buyer_side)

    factory_side = client.get("/api/reviews", headers=auth(client, "factory")).json()
    assert any(r["record_id"] == record_id for r in factory_side)


def test_reading_a_document_writes_nothing_to_the_ledger(client):
    """
    Opening a file is a read. The flag is served so the interface can say so
    beside the button that does write, rather than leaving somebody to find out
    which of the two puts their name on the chain.
    """
    buyer = auth(client, "buyer")
    record_id = a_record(client, "buyer")

    def height() -> int:
        summary = client.get("/api/ledger/channels", headers=buyer).json()
        return next(c["height"] for c in summary if c["channel"] == "documents-apex-primark")

    before = height()
    body = client.get(f"/api/records/{record_id}/preview", headers=buyer).json()
    assert body["writes_to_ledger"] is False
    assert height() == before
