"""
The document preview, and the line it draws.

The preview is the one place in this product that serves document *content* to
somebody who is not the document's owner, so it is the one place where a
mistake leaks a worker's data rather than merely showing the wrong label. These
tests are about that boundary, and specifically about the failure mode a
preview invites: sending a value and trusting the client not to draw it.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.redaction import classify, label_for, redact


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("breadcrumbs-preview")
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


# ------------------------------------------------------------ classification --

def test_people_are_identity_columns():
    for field in ("worker_ref", "technician_ref", "inspector_ref"):
        assert classify(field) == "identity"


def test_identity_is_recognised_by_hint_not_only_by_the_list():
    """A corpus that grows a new personal column must not need a code change."""
    assert classify("supervisor_name") == "identity"
    assert classify("worker_national_id") == "identity"
    assert classify("bank_account_no") == "identity"


def test_structural_columns_are_open_and_figures_are_not():
    assert classify("storage_zone") == "open"
    assert classify("paid_on") == "open"
    assert classify("net_pay_bdt") == "sensitive"


def test_labels_are_readable():
    assert label_for("net_pay_bdt") == "Net pay (BDT)"
    assert label_for("days_worked") == "Days worked"


# ------------------------------------------------------------------ redaction --

ROWS = [
    {"worker_ref": "W-001", "basic_bdt": 15921.82, "net_pay_bdt": 17400.61, "paid_on": "2025-07-01"},
    {"worker_ref": "W-002", "basic_bdt": 19229.01, "net_pay_bdt": 20017.42, "paid_on": "2025-07-01"},
]


def test_withheld_values_are_absent_rather_than_marked():
    """
    The whole point. A preview that sends the value and flags it as hidden has
    leaked it to anyone who opens the network tab.
    """
    out = redact(ROWS, is_owner=False, granted_fields={"net_pay_bdt"})
    for row in out["rows"]:
        assert "worker_ref" not in row
        assert "basic_bdt" not in row
        assert row["net_pay_bdt"] in (17400.61, 20017.42)


def test_a_grant_does_not_open_an_identity_column():
    """A licence to check one figure is not a licence to learn whose it is."""
    out = redact(ROWS, is_owner=False, granted_fields={"worker_ref"})
    worker = next(c for c in out["columns"] if c["name"] == "worker_ref")
    assert worker["visible"] is False
    assert all("worker_ref" not in row for row in out["rows"])


def test_the_owner_sees_its_own_document():
    out = redact(ROWS, is_owner=True, granted_fields=set())
    assert all(c["visible"] for c in out["columns"])
    assert out["rows"][0]["worker_ref"] == "W-001"


def test_every_column_is_described_even_when_withheld():
    """The shape of what is hidden is the part worth showing."""
    out = redact(ROWS, is_owner=False, granted_fields=set())
    assert {c["name"] for c in out["columns"]} == set(ROWS[0])
    assert out["total_columns"] == 4


def test_columns_come_from_every_row_not_only_the_first():
    rows = [{"a": 1}, {"a": 2, "b": 3}]
    out = redact(rows, is_owner=True, granted_fields=set())
    assert [c["name"] for c in out["columns"]] == ["a", "b"]


def test_limit_bounds_the_rows_but_not_the_column_list():
    rows = ROWS * 20
    out = redact(rows, is_owner=True, granted_fields=set(), limit=3)
    assert out["shown_rows"] == 3
    assert out["total_rows"] == 40
    assert out["total_columns"] == 4


# ------------------------------------------------------------------ endpoint --

def test_owner_preview_shows_the_whole_document(client):
    factory = auth(client, "factory")
    records = client.get("/api/records", headers=factory).json()
    record = next(r for r in records if r["record_type"] == "payroll_register")

    body = client.get(f"/api/records/{record['record_id']}/preview", headers=factory).json()
    assert body["access"] == "owner"
    assert body["readable_columns"] == body["total_columns"]
    assert any("worker_ref" in row for row in body["rows"])


def test_buyer_preview_withholds_the_worker_and_the_ungranted_figures(client):
    buyer = auth(client, "buyer")
    records = client.get("/api/records", headers=buyer).json()
    record = next(r for r in records if r["record_type"] == "payroll_register")

    body = client.get(f"/api/records/{record['record_id']}/preview", headers=buyer).json()
    assert body["access"] == "granted"
    assert body["readable_columns"] < body["total_columns"]

    withheld = {c["name"] for c in body["columns"] if not c["visible"]}
    assert "worker_ref" in withheld
    for row in body["rows"]:
        assert not withheld & set(row), "a withheld column reached the client"
    for field in body["granted_fields"]:
        assert all(field in row for row in body["rows"])


def test_a_record_outside_scope_is_a_404_not_a_403(client):
    """
    Same choice the sibling endpoints make: "you may not see this" and "there is
    no such record" have to be indistinguishable, or the refusal confirms the
    document exists.
    """
    factory = auth(client, "factory")
    buyer = auth(client, "buyer")
    reachable = {r["record_id"] for r in client.get("/api/records", headers=buyer).json()}
    hidden = next(
        r["record_id"] for r in client.get("/api/records", headers=factory).json()
        if r["record_id"] not in reachable
    )
    assert client.get(f"/api/records/{hidden}/preview", headers=buyer).status_code == 404


def test_the_regulator_cannot_preview_anything(client):
    """Its whole screen promises it sees no factory data."""
    regulator = auth(client, "regulator")
    factory = auth(client, "factory")
    record = client.get("/api/records", headers=factory).json()[0]
    r = client.get(f"/api/records/{record['record_id']}/preview", headers=regulator)
    assert r.status_code == 403


def test_record_fields_marks_identity_columns_as_unrequestable(client):
    buyer = auth(client, "buyer")
    fields = client.get("/api/record-fields", headers=buyer).json()

    payroll = {f["name"]: f for f in fields["payroll_register"]}
    assert payroll["worker_ref"]["requestable"] is False
    assert payroll["net_pay_bdt"]["requestable"] is True
    assert payroll["net_pay_bdt"]["label"] == "Net pay (BDT)"
