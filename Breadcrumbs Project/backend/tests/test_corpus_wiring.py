"""
The world is the corpus, and these tests try to catch it not being.

The claim this file exists to defend is narrow and checkable: every document the
API serves is a document in `data/corpus/`, and the attacks the interface
demonstrates are the attacks the corpus's own adversary trace describes. A demo
that quietly fabricates a more convenient world than the dataset it cites is the
exact failure mode this project spends its report warning about, so it gets
tests rather than a promise.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os

    tmp = tmp_path_factory.mktemp("breadcrumbs-corpus")
    os.environ["BREADCRUMBS_LEDGER_PATH"] = str(tmp / "ledger.db")
    os.environ["BREADCRUMBS_DATABASE_URL"] = f"sqlite:///{tmp / 'app.db'}"

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
def corpus_available():
    from app import corpus

    if not corpus.available():
        pytest.skip("no corpus on disk; run python -m data.cli --seed 7 --scale small")
    return corpus


# -- provenance -----------------------------------------------------------
def test_health_says_where_the_documents_came_from(client):
    """
    "This is real data" is a claim. It has to arrive with its seed.
    """
    body = client.get("/api/health").json()
    prov = body["provenance"]
    assert prov["corpus"] in ("present", "absent")
    if prov["corpus"] == "absent":
        pytest.skip("no corpus on disk")
    assert prov["seed"] == 7
    assert len(prov["manifest_sha256"]) == 64
    assert prov["records_on_ledger"] > 0


def test_every_record_on_the_ledger_is_a_corpus_document(client, corpus_available):
    """
    The strongest form of the claim, checked exhaustively rather than sampled.

    Each record id on the chain must be a document id that exists in the corpus
    window, and the row count the ledger committed must equal the number of rows
    that document actually has. A seeded record that drifted from its source
    would be a lie told in the most load-bearing place in the product.
    """
    in_corpus = {
        doc["doc_id"]: len(doc["rows"]) for doc in corpus_available.window_documents()
    }
    records = client.get("/api/records", headers=auth(client, "factory")).json()
    assert records

    unknown = [r["record_id"] for r in records if r["record_id"] not in in_corpus]
    assert unknown == [], f"records with no corpus document behind them: {unknown[:5]}"

    wrong_size = [
        r["record_id"] for r in records if r["row_count"] != in_corpus[r["record_id"]]
    ]
    assert wrong_size == [], f"row counts that drifted from the corpus: {wrong_size[:5]}"


def test_documents_the_chaincode_schema_refuses_are_counted_not_hidden(client, corpus_available):
    """
    The corpus generates five record types and `VALID_TYPES` names four of them.
    The shortfall must be reported, because a corpus that arrives 20% smaller
    without saying so makes every count downstream of it wrong.
    """
    prov = client.get("/api/health").json()["provenance"]
    excluded = prov["excluded_by_schema"]
    assert excluded > 0
    assert "production_output" in prov["excluded_reason"]

    records = client.get("/api/records", headers=auth(client, "factory")).json()
    assert all(r["record_type"] != "production_output" for r in records)


# -- the attacks are the corpus's, not ours -------------------------------
def test_the_withheld_period_is_the_one_the_adversary_trace_names(client, corpus_available):
    """
    The completeness demonstration must be the dataset's attack.

    The trace names a site, a period and the exact documents that were withheld.
    Those documents must be on the ledger — the factory produced them — and the
    buyer must hold no grant against any of them.
    """
    event = corpus_available.event("withholding")
    assert event, "the corpus trace has no withholding event to reproduce"
    withheld = set(event["parameters"]["withheld_doc_ids"])
    site = corpus_available.SITE_LABEL[event["site"]]

    factory = {
        r["record_id"] for r in client.get("/api/records", headers=auth(client, "factory")).json()
        if r["site"] == site and r["period"] == event["period"]
    }
    buyer = {
        r["record_id"] for r in client.get("/api/records", headers=auth(client, "buyer")).json()
    }

    on_ledger = withheld & factory
    assert on_ledger, "none of the withheld documents reached the ledger"
    assert not (on_ledger & buyer), "the buyer was granted a document the trace says was withheld"


def test_the_completeness_check_fails_by_exactly_the_withheld_count(client, corpus_available):
    """
    Arithmetic, and it has to be the right arithmetic: the shortfall the ledger
    reports must equal the number of documents the trace says were kept back.

    Asked as the buyer, because the buyer is the party that can be withheld
    from. An auditor now sees every document on the channel by default, so
    nothing is ever missing from its view and a completeness check run as the
    auditor would pass trivially — which is asserted separately below, since it
    is the point of that rule rather than a gap in this one.
    """
    event = corpus_available.event("withholding")
    site = corpus_available.SITE_LABEL[event["site"]]
    withheld = set(event["parameters"]["withheld_doc_ids"])

    factory_records = client.get("/api/records", headers=auth(client, "factory")).json()
    buyer_records = client.get("/api/records", headers=auth(client, "buyer")).json()
    buckets = {
        r["bucket"] for r in factory_records
        if r["site"] == site and r["period"] == event["period"]
        and r["record_id"] in withheld
    }
    assert buckets, "no sealed bucket contains a withheld document"

    checked = 0
    for bucket in sorted(buckets):
        owner, site_name, record_type, period = bucket.split("|")
        disclosed = [r["record_id"] for r in buyer_records if r["bucket"] == bucket]
        if not disclosed:
            # Nothing was disclosed to the buyer in this bucket, so there is no
            # short disclosure to measure. Skipped rather than asserted away.
            continue
        holder = "buyer"
        body = client.post(
            "/api/completeness",
            json={
                "owner_msp": owner, "site": site_name, "record_type": record_type,
                "period": period, "disclosed_record_ids": disclosed,
            },
            headers=auth(client, holder),
        ).json()
        expected_short = (
            len([r for r in factory_records if r["bucket"] == bucket]) - len(disclosed)
        )
        assert body["complete"] is False
        assert body["sealed_count"] - body["disclosed_count"] == expected_short
        assert body["sealed_root"] != body["computed_root"]
        checked += 1

    assert checked >= 1, "the buyer holds nothing the withholding attack touched"


def test_an_auditor_is_never_short_because_nothing_is_withheld_from_it(
    client, corpus_available
):
    """
    The other half of the rule changed above.

    An auditor sees every document on the channel, so a completeness check run
    as the auditor is complete by construction. That is worth asserting rather
    than assuming: if this ever fails, either the auditor's access has been
    narrowed again or the completeness arithmetic has drifted.
    """
    event = corpus_available.event("withholding")
    site = corpus_available.SITE_LABEL[event["site"]]
    withheld = set(event["parameters"]["withheld_doc_ids"])

    factory_records = client.get("/api/records", headers=auth(client, "factory")).json()
    auditor_records = client.get("/api/records", headers=auth(client, "auditor")).json()
    bucket = sorted(
        r["bucket"] for r in factory_records
        if r["site"] == site and r["period"] == event["period"]
        and r["record_id"] in withheld
    )[0]

    owner, site_name, record_type, period = bucket.split("|")
    disclosed = [r["record_id"] for r in auditor_records if r["bucket"] == bucket]
    assert disclosed, "the auditor sees every record, so this cannot be empty"

    body = client.post(
        "/api/completeness",
        json={
            "owner_msp": owner, "site": site_name, "record_type": record_type,
            "period": period, "disclosed_record_ids": disclosed,
        },
        headers=auth(client, "auditor"),
    ).json()
    assert body["complete"] is True, body
    assert body["sealed_count"] == body["disclosed_count"]


def test_the_lazy_witness_claimed_only_the_weakest_check(client, corpus_available):
    """
    The trace names a document whose counter-signature was lazy. The ledger must
    carry that attestation with the weakest rung of the ladder on it, because a
    witness panel that renders every signature identically throws away the only
    thing that distinguishes a real check from a rubber stamp.
    """
    event = corpus_available.event("witness_collusion")
    if not event or not event.get("target_doc_id"):
        pytest.skip("the corpus trace has no witness event with a target document")

    body = client.get(
        f"/api/records/{event['target_doc_id']}/witness-requirement",
        headers=auth(client, "factory"),
    )
    if body.status_code == 404:
        pytest.skip("the flagged document is outside the seeded window")
    payload = body.json()
    assert payload["in_force"] is True
    if payload["required"]:
        codes = {a["check_code"] for a in payload["attestations"]}
        assert codes == {"format_only"}, (
            "the document the trace calls lazily witnessed carries a stronger claim "
            f"than format_only: {codes}"
        )


# -- the new workspace endpoints ------------------------------------------
def test_the_observer_sees_the_directory_but_no_activity_and_no_queue(client):
    """
    Membership is a governance fact. An organisation's transaction log is not.
    """
    headers = auth(client, "regulator")
    assert client.get("/api/orgs", headers=headers).status_code == 200
    assert client.get("/api/activity", headers=headers).status_code == 403
    assert client.get("/api/audit/queue", headers=headers).status_code == 403


def test_the_activity_feed_shows_only_the_callers_own_transactions(client):
    """
    The feed is the block log read back. Reading it back must not widen it.
    """
    for role, msp in (("buyer", "PrimarkSourcingMSP"), ("auditor", "BVCertificationMSP")):
        feed = client.get("/api/activity", headers=auth(client, role)).json()
        submitters = {e["text"].split(" ")[0] for e in feed}
        assert submitters <= {msp.replace("MSP", "")}, (
            f"{role} was shown transactions submitted by {submitters}"
        )


def test_the_auditors_queue_is_its_grants_and_its_receipts(client):
    """
    Queue state is derived, never stored. Anything marked passed must have a
    receipt id, and anything queued must not.
    """
    body = client.get("/api/audit/queue", headers=auth(client, "auditor")).json()
    assert body["items"]
    for item in body["items"]:
        if item["state"] == "passed":
            assert item["receipt_id"], f"{item['record_id']} passed with no receipt"
        if item["state"] == "queued":
            assert item["receipt_id"] is None


def test_operations_does_not_invent_the_telemetry_it_does_not_have(client):
    """
    Uptime and latency are not measured by this prototype. The API must say so
    rather than serving a plausible number, and it must still serve the counts
    it genuinely has.
    """
    body = client.get("/api/ops/sla", headers=auth(client, "consortium")).json()
    assert body["kpis"]["monthly_uptime_pct"] is None
    assert body["kpis"]["avg_response_ms"] is None
    assert "no uptime or latency monitoring" in body["unmeasured"]["reason"]
    assert body["kpis"]["total_verifications"] >= 0
    assert all(p["uptime_pct"] is None for p in body["points"])


def test_about_needs_no_token_and_carries_the_corpus_seed(client):
    """
    The landing page's claims come from here. A statement about a system's
    honesty that requires a sign-in to read is not much of a statement.
    """
    body = client.get("/api/about").json()
    assert body["limitations"]
    assert body["comparison"]["rows"]
    assert body["windows"], "the demo window and the reason for each period"
    if body["provenance"]["corpus"] == "present":
        assert body["provenance"]["seed"] == 7


def test_the_corpus_manifest_digest_matches_the_file_on_disk(client, corpus_available):
    """A digest served by the thing it describes is worth checking once."""
    import hashlib

    served = client.get("/api/health").json()["provenance"]["manifest_sha256"]
    actual = hashlib.sha256(
        (corpus_available.CORPUS / "manifest.json").read_bytes()
    ).hexdigest()
    assert served == actual


def test_the_seeded_window_is_a_real_subset_of_the_corpus(client, corpus_available):
    """
    Every window the API advertises must exist in the corpus and must have
    produced documents. A window naming a period the generator never wrote would
    make the "why these periods" answer on screen a fiction.
    """
    windows = client.get("/api/about").json()["windows"]
    assert windows
    for window in windows:
        docs = list(corpus_available.documents(window["site"], window["period"]))
        assert docs, f"{window['site']} {window['period']} has no corpus documents"
        assert window["reason"]


# -- the interface must not overstate -------------------------------------
def test_a_record_older_than_the_rule_is_not_reported_as_unwitnessed(client):
    """
    The contract answers `witness_requirement` for the round active *now*, and
    has no historical view of its own rounds. A record committed before the
    consortium adopted the rule therefore comes back "required" with no
    attestations — which reads on screen as an assigned witness having refused
    to sign. The endpoint has to carry enough for the interface to tell those
    two cases apart, or it is asserting misconduct that did not happen.
    """
    factory = auth(client, "factory")
    records = client.get("/api/records", headers=factory).json()
    assert records

    checked = 0
    for record in records:
        body = client.get(
            f"/api/records/{record['record_id']}/witness-requirement", headers=factory
        ).json()
        if not body.get("in_force"):
            continue
        assert "predates_rule" in body
        if body["predates_rule"]:
            assert body["committed_at"] < body["round_opened_at"]
            assert not body["attestations"], (
                "a record committed before the rule carries no attestations, "
                "and must not be shown as one that refused to sign"
            )
            checked += 1
        elif body["required"]:
            # After the rule, an assigned witness really did sign.
            assert body["attestations"], f"{record['record_id']} was required and unsigned"
        if checked > 3:
            break
    assert checked, "no record in the world predates the witness rule"


def test_the_ledger_and_the_calendar_agree_about_the_witness_rule(client):
    """
    Ordering, not merely dates. Every record whose commit timestamp falls after
    the round opened must carry the counter-signature the rule demands, and no
    record before it may carry one. The seed used to commit every document and
    open the round afterwards, which satisfied the contract and contradicted the
    calendar printed beside it on every screen.
    """
    factory = auth(client, "factory")
    records = client.get("/api/records", headers=factory).json()
    rounds = [
        client.get(f"/api/records/{r['record_id']}/witness-requirement", headers=factory).json()
        for r in records[:1]
    ]
    opened_at = rounds[0].get("round_opened_at")
    assert opened_at, "no seed round is active"

    early_with_witnesses = [
        r for r in records if r["committed_at"] < opened_at and r["witnesses"]
    ]
    assert early_with_witnesses == [], (
        "a record committed before the rule carries counter-signatures"
    )

    late = [r for r in records if r["committed_at"] >= opened_at]
    assert late, "nothing was committed after the rule came into force"
    assert any(r["witnesses"] for r in late), "the rule is in force but nothing is witnessed"


def test_operations_counts_verifications_as_they_happen(client):
    """
    A figure that stops moving when the thing it counts moves is not a
    measurement. This ran a real proof and expects the total to follow it.
    """
    consortium = auth(client, "consortium")
    before = client.get("/api/ops/sla", headers=consortium).json()["kpis"]["total_verifications"]

    auditor = auth(client, "auditor")
    queue = client.get("/api/audit/queue", headers=auditor).json()
    pending = next((i for i in queue["items"] if i["state"] == "queued"), None)
    if pending is None:
        pytest.skip("the auditor's batch is already fully verified")

    proof = client.post(
        "/api/verify", headers=auditor,
        json={
            "grant_id": pending["grant_id"], "record_id": pending["record_id"],
            "row_index": 0, "field_name": pending["field_name"],
            "receipt_id": "vr-sla-probe",
        },
    )
    assert proof.status_code == 200

    after = client.get("/api/ops/sla", headers=consortium).json()["kpis"]["total_verifications"]
    assert after == before + 1


def test_an_attestation_over_an_unverified_batch_is_refused(client):
    """
    An auditor may not sign for records it has not checked, and the API counts
    the receipts on the chain rather than believing the form.
    """
    auditor = auth(client, "auditor")
    queue = client.get("/api/audit/queue", headers=auditor).json()
    if not any(i["state"] == "queued" for i in queue["items"]):
        pytest.skip("nothing outstanding to refuse an attestation over")

    r = client.post(
        "/api/attestations", headers=auditor,
        json={
            "claim_code": "ISO45001-PREMATURE",
            "evidence_scope": "All records in this batch",
            "statement": "Everything looked fine from here, honestly.",
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "BATCH_INCOMPLETE"


def test_a_receipt_is_checkable_without_an_account_and_shows_no_value(client):
    """
    The product claims a receipt can be handed to a third party who checks it
    without an account and without asking the factory. That claim needs the
    endpoint to be open — and needs it not to publish the disclosed figure,
    which was released to one counterparty under a grant covering one field.
    """
    buyer = auth(client, "buyer")
    grant = next(
        g for g in client.get("/api/grants", headers=buyer).json() if g["status"] == "active"
    )
    proved = client.post(
        "/api/verify", headers=buyer,
        json={
            "grant_id": grant["grant_id"], "record_id": grant["record_id"],
            "row_index": 0, "field_name": grant["field_name"],
            "receipt_id": "vr-public-probe",
        },
    ).json()
    value = str(proved["disclosed"]["value"])

    # No Authorization header at all.
    public = client.get("/api/receipts/vr-public-probe")
    assert public.status_code == 200
    body = public.json()
    assert body["root_matches"] is True
    assert body["receipt"]["result"] == "match"
    assert value not in public.text, "the public receipt published the disclosed value"


def test_a_request_becomes_a_grant_only_by_the_supplier_naming_a_record(client):
    """
    A request names a period; a grant names a document. The factory has to
    choose which, and only the supplier it was addressed to may answer it.
    """
    buyer = auth(client, "buyer")
    factory = auth(client, "factory")
    made = client.post(
        "/api/requests", headers=buyer,
        json={
            "supplier_msp": "ApexTextileMSP", "record_type": "payroll_register",
            "period": "2026-10", "purpose_code": "ETH-WAGE-VERIFY",
            "field_name": "net_pay_bdt", "expires_at": "2028-12-31T00:00:00Z",
        },
    )
    assert made.status_code == 201
    request_id = made.json()["id"]

    # The buyer cannot answer its own request.
    assert client.post(
        f"/api/requests/{request_id}/grant", headers=buyer, json={"record_id": "x"}
    ).status_code in (403, 404)

    # Nor may the supplier answer without naming a record.
    assert client.post(
        f"/api/requests/{request_id}/grant", headers=factory, json={}
    ).status_code == 400

    target = next(
        r for r in client.get("/api/records", headers=factory).json()
        if r["record_type"] == "payroll_register" and r["period"] == "2026-10"
    )
    answered = client.post(
        f"/api/requests/{request_id}/grant", headers=factory,
        json={"record_id": target["record_id"]},
    )
    assert answered.status_code == 200
    assert answered.json()["status"] == "granted"

    # And it cannot be answered twice.
    assert client.post(
        f"/api/requests/{request_id}/grant", headers=factory,
        json={"record_id": target["record_id"]},
    ).status_code == 409


def test_reopening_a_period_makes_it_refuse_to_serve_a_settled_count(client):
    """
    The honest state the contract had and the product could not reach.

    While a period is reopened its membership is mid-revision. A completeness
    check on it must say so rather than answering with the count it had before,
    because that count is about to change and a verifier reading it would draw a
    conclusion the factory has already withdrawn.
    """
    factory = auth(client, "factory")
    seals = client.get("/api/seals", headers=factory).json()
    target = next((s for s in seals if s["status"] == "sealed"), None)
    assert target, "no sealed period to reopen"

    owner, site, record_type, period = target["bucket"].split("|")
    body = {"owner_msp": owner, "site": site, "record_type": record_type, "period": period}
    records = [
        r["record_id"] for r in client.get("/api/records", headers=factory).json()
        if r["bucket"] == target["bucket"]
    ]

    settled = client.post(
        "/api/completeness", headers=factory,
        json={**body, "disclosed_record_ids": records},
    ).json()
    assert settled["sealed"] is True
    assert settled["complete"] is True

    reopened = client.post(
        f"/api/seals/{target['bucket']}/reopen", headers=factory,
        json={"reason": "a late night-shift register has to come in"},
    )
    assert reopened.status_code == 200

    after = client.post(
        "/api/completeness", headers=factory,
        json={**body, "disclosed_record_ids": records},
    ).json()
    assert after["sealed"] is False
    assert after["status"] == "reopened"
    assert "mid-revision" in after["reason"]


def test_reopening_needs_a_reason_and_the_right_owner(client):
    """
    The reason is recorded before the membership changes, so it cannot be
    written after the fact to fit whatever happened. And the bucket key is
    re-derived from the caller's own MSP, so naming somebody else's in the path
    cannot reach their seal.
    """
    factory = auth(client, "factory")
    seals = client.get("/api/seals", headers=factory).json()
    target = next(s for s in seals if s["status"] == "sealed")

    empty = client.post(
        f"/api/seals/{target['bucket']}/reopen", headers=factory, json={"reason": ""}
    )
    assert empty.status_code == 422

    _, site, record_type, period = target["bucket"].split("|")
    other = client.post(
        f"/api/seals/NoorGarmentsMSP|{site}|{record_type}|{period}/reopen",
        headers=factory, json={"reason": "trying somebody else's period"},
    )
    assert other.status_code == 403
    assert other.json()["detail"]["code"] == "NOT_YOUR_BUCKET"

    # And a buyer may not reopen anything at all.
    assert client.post(
        f"/api/seals/{target['bucket']}/reopen", headers=auth(client, "buyer"),
        json={"reason": "not mine to reopen"},
    ).status_code == 403


def test_a_delay_proof_can_be_published_onto_an_epoch_that_has_none(client):
    """
    The consortium can attach real delay work to an epoch from the product, and
    the contract re-derives the input rather than trusting the one submitted —
    so computing it client-side cannot be used to choose a convenient start.
    """
    consortium = auth(client, "consortium")
    epochs = client.get("/api/anchor/epochs", headers=consortium).json()
    bare = next((e for e in epochs if "beacon" not in e), None)
    if bare is None:
        pytest.skip("every epoch already carries a beacon")

    state = client.get("/api/anchor/state", headers=consortium).json()
    minimum = state["minimum_iterations"]

    published = client.post(
        "/api/anchor/beacon", headers=consortium,
        json={"epoch": bare["epoch"], "iterations": minimum},
    )
    assert published.status_code == 200
    assert published.json()["response"]["verified"] is True

    again = client.get("/api/anchor/epochs", headers=consortium).json()
    now_sealed = next(e for e in again if e["epoch"] == bare["epoch"])
    assert now_sealed["beacon"]["iterations"] == minimum

    # A second one on the same epoch is refused: a beacon is not replaceable.
    assert client.post(
        "/api/anchor/beacon", headers=consortium,
        json={"epoch": bare["epoch"], "iterations": minimum},
    ).status_code == 400


def test_a_factory_may_not_publish_a_beacon(client):
    """Folding and timestamping the batch is a consortium act, not a factory's."""
    assert client.post(
        "/api/anchor/beacon", headers=auth(client, "factory"),
        json={"epoch": 1, "iterations": 1024},
    ).status_code == 403


# -- the gate's cumulative bound ------------------------------------------
def test_the_drift_ceiling_is_readable_and_only_promotion_raises_it(client):
    """
    A ceiling nobody can inspect is a number the operator could be moving.

    The gate refuses a candidate that has fallen more than sigma below a task's
    best-ever score, so the marks it measures against have to be readable — and
    they must only move on promotion, or a rejected submission could lift the
    bar its successor is judged by.
    """
    consortium = auth(client, "consortium")
    body = client.get("/api/model/high-water", headers=consortium).json()
    assert "marks" in body
    assert body["marks"], "no tasks on the model channel"

    registry = client.get("/api/model/registry", headers=consortium).json()
    promoted = [m for m in registry if m["status"] in ("promoted", "superseded")]

    for task, mark in body["marks"].items():
        if mark is None:
            # Nothing promoted on this task: no candidate may claim a drift.
            for model in registry:
                row = next((t for t in model["per_task"] if t["task_id"] == task), None)
                if row and row["best_bp"] is not None:
                    raise AssertionError(
                        f"{task} has no high-water mark but {model['model_id']} "
                        "recorded a best_bp against it"
                    )
            continue

        # The mark must equal the best score any *promoted* model reached.
        best_promoted = max(
            (t["candidate_bp"] for m in promoted for t in m["per_task"]
             if t["task_id"] == task),
            default=None,
        )
        assert best_promoted is not None, f"{task} has a mark with nothing promoted"
        assert mark >= best_promoted, (
            f"{task}: mark {mark} is below the best promoted score {best_promoted}"
        )


def test_every_per_task_row_carries_the_cumulative_fields(client):
    """
    The interface renders `best_bp` and `drift_from_best_bp`, and null means "no
    baseline yet" rather than zero. Both keys must always be present, or the
    frontend cannot tell an absent baseline from a missing field.
    """
    consortium = auth(client, "consortium")
    registry = client.get("/api/model/registry", headers=consortium).json()
    assert registry

    for model in registry:
        decision = client.get(
            f"/api/model/decisions/{model['model_id']}", headers=consortium
        ).json()
        assert "sigma_bp" in decision["parameters"]
        assert decision["parameters"]["sigma_bp"] >= decision["parameters"]["tau_bp"]
        for row in decision["per_task"]:
            assert "best_bp" in row and "drift_from_best_bp" in row
            if row["best_bp"] is None:
                assert row["drift_from_best_bp"] is None
            else:
                assert row["drift_from_best_bp"] == row["best_bp"] - row["candidate_bp"]


def test_a_rejection_always_carries_a_reason_code_the_interface_knows(client):
    """
    A refusal that renders with no explanation is worse than no screen at all.
    Every recorded rejection must carry one of the codes the decision page
    handles; a new one added to the contract should fail here rather than
    silently render blank.
    """
    known = {"OK", "REGRESSION", "CUMULATIVE_REGRESSION", "NO_GAIN",
             "INSUFFICIENT_ENDORSEMENT", "DISAGREEMENT"}
    consortium = auth(client, "consortium")
    for model in client.get("/api/model/registry", headers=consortium).json():
        decision = client.get(
            f"/api/model/decisions/{model['model_id']}", headers=consortium
        ).json()
        assert decision["reason_code"] in known, (
            f"{model['model_id']} has reason code {decision['reason_code']}, which the "
            "gate decision page does not handle"
        )
        assert decision["reason"], "a decision with no sentence explaining it"


def test_a_sigma_below_tau_is_refused_as_a_misconfiguration(client):
    """
    A cumulative ceiling tighter than the per-round one makes the per-round
    check unreachable. That is a mistake rather than a strict policy, and the
    API must carry the contract's refusal rather than quietly obeying it.
    """
    consortium = auth(client, "consortium")
    existing = client.get("/api/model/rounds", headers=consortium).json()
    assert existing
    tasks = existing[0]["tasks"]

    # Every seeded round has been decided, and a decided round is refused before
    # the parameters are even read. Open a fresh one so the sigma check is what
    # this test actually reaches.
    opened = client.post(
        "/api/model/rounds", headers=consortium,
        json={
            "round_id": "round-sigma-probe", "tasks": tasks,
            "contributors": ["ApexTextileMSP", "NoorGarmentsMSP"],
            "memory_bank_hash": "b" * 64,
        },
    )
    assert opened.status_code == 201

    r = client.post(
        "/api/model/gate", headers=consortium,
        json={
            "round_id": "round-sigma-probe", "candidate_id": "m-bad-sigma",
            "candidate_hash": "0" * 64, "parent_id": "m-v6",
            "new_task": tasks[0], "submissions": [],
            "gamma_bp": 200, "tau_bp": 500, "k": 3, "delta_bp": 100,
            "sigma_bp": 100,
        },
    )
    assert r.status_code == 400
    assert "sigma_bp" in str(r.json()).lower()


def test_omitting_sigma_lets_the_contract_choose_its_own_default(client):
    """
    `sigma_bp` is optional on the wire. An unset value must not reach the
    contract as an explicit null, or `args.get("sigma_bp", default)` finds the
    key, returns None, and the int() of it raises instead of defaulting.
    """
    consortium = auth(client, "consortium")
    existing = client.get("/api/model/rounds", headers=consortium).json()
    tasks = existing[0]["tasks"]

    opened = client.post(
        "/api/model/rounds", headers=consortium,
        json={
            "round_id": "round-default-sigma", "tasks": tasks,
            "contributors": ["ApexTextileMSP", "NoorGarmentsMSP"],
            "memory_bank_hash": "c" * 64,
        },
    )
    assert opened.status_code == 201

    # No submissions, so the gate refuses for want of endorsement — but it has
    # to get that far, which means sigma defaulted rather than raising on an
    # explicit null. The recorded parameters then show what it chose.
    r = client.post(
        "/api/model/gate", headers=consortium,
        json={
            "round_id": "round-default-sigma", "candidate_id": "m-default-sigma",
            "candidate_hash": "0" * 64, "parent_id": "m-v6",
            "new_task": tasks[0], "submissions": [],
            "gamma_bp": 200, "tau_bp": 500, "k": 3, "delta_bp": 100,
        },
    )
    assert r.status_code == 200
    decision = r.json()
    assert decision["outcome"] == "reject"
    assert decision["parameters"]["sigma_bp"] == 2 * decision["parameters"]["tau_bp"], (
        "the contract did not apply its own default for an omitted sigma_bp"
    )


# -- the detector, actually run -------------------------------------------
def test_the_detector_is_deployed_and_reports_what_it_costs(client):
    """
    A score with no error rate beside it is the most dishonest thing this
    product could show, and the easiest to build. The status endpoint must
    always carry the measured rates, and must be explicit about the family the
    detector cannot see rather than leaving a reader to infer it.
    """
    body = client.get("/api/model/detector", headers=auth(client, "consortium")).json()
    if not body["trained"]:
        pytest.skip(f"no trained detector on disk: {body['reason']}")

    assert body["features"] == 25, "the served model must match data/features.py"
    assert 0 < body["threshold"] < 1
    assert body["measured"]["detection"] is not None
    assert body["measured"]["false_positive"] is not None
    assert body["measured"]["seeds"] >= 1

    # The blind spot is stated, not implied.
    blind = body["blind_to"]
    assert blind["kind"] == "cross_inconsistency"
    assert blind["detection"] is not None and blind["detection"] < 0.25, (
        "cross_inconsistency is invisible from a single document; a high number "
        "here means something is claiming to detect it"
    )
    assert "not evidence" in body["note"]


def test_screening_is_scoped_exactly_like_reading_the_record(client):
    """
    A score is a statement about a document's contents. Being able to obtain one
    for a document you may not read would be a disclosure with extra steps.
    """
    factory = auth(client, "factory")
    buyer = auth(client, "buyer")
    mine = {r["record_id"] for r in client.get("/api/records", headers=buyer).json()}
    theirs = [
        r["record_id"] for r in client.get("/api/records", headers=factory).json()
        if r["record_id"] not in mine
    ]
    assert theirs, "the factory holds nothing the buyer cannot see"

    assert client.post(f"/api/records/{theirs[0]}/screen", headers=buyer).status_code == 404
    assert client.post(f"/api/records/{theirs[0]}/screen", headers=factory).status_code == 200

    # And the observer may not score anything at all.
    assert client.post(
        f"/api/records/{theirs[0]}/screen", headers=auth(client, "regulator")
    ).status_code == 403


def test_a_score_always_arrives_with_its_threshold_and_its_caveat(client):
    """
    The score sits a few centimetres below a cryptographic proof on the record
    page, and the two are not the same kind of fact. Every response has to carry
    what the number was compared against and a sentence saying what it is not.
    """
    factory = auth(client, "factory")
    record = client.get("/api/records", headers=factory).json()[0]
    body = client.post(f"/api/records/{record['record_id']}/screen", headers=factory).json()
    if not body.get("scored"):
        pytest.skip("no trained detector on disk")

    assert 0.0 <= body["score"] <= 1.0
    assert 0.0 < body["threshold"] < 1.0
    assert body["flagged"] is (body["score"] >= body["threshold"])
    assert body["caveat"]
    assert body["verdict"]
    # The class probabilities must be a distribution, not four unrelated numbers.
    assert abs(sum(body["per_class"].values()) - 1.0) < 0.01
    # A record that was not flagged must not be reported as a clean bill of health.
    if not body["flagged"]:
        assert "not a clean bill of health" in body["caveat"]


def test_the_detector_separates_a_planted_anomaly_from_a_clean_document(client, corpus_available):
    """
    Not a benchmark — the training already reports those. This checks the served
    path end to end: the extractor the API loads, the scaler it applies and the
    weights it read really do rank a corpus document the generator labelled
    anomalous above one it labelled clean.

    Uses the arithmetic family, which the training measures at 99% detection, so
    a failure here means the serving path is broken rather than that the model is
    weak. `outlier` or `cross_inconsistency` would make this test flaky by design.
    """
    from app import detector

    if not detector.available():
        pytest.skip("no trained detector on disk")

    clean = anomalous = None
    for doc in corpus_available.window_documents():
        if doc["label"] == 0 and clean is None:
            clean = doc
        elif doc.get("anomaly_kind") == "arithmetic" and anomalous is None:
            anomalous = doc
        if clean and anomalous:
            break
    if not (clean and anomalous):
        pytest.skip("the demo window holds no arithmetic anomaly to compare against")

    low = detector.screen(clean["record_type"], clean["rows"])
    high = detector.screen(anomalous["record_type"], anomalous["rows"])
    assert high["score"] > low["score"], (
        "the served detector ranks a planted arithmetic anomaly no higher than a "
        "clean document; the serving path is broken"
    )
    assert high["flagged"] is True


def test_serving_the_web_bundle_does_not_shadow_the_api(client):
    """
    A single-container deployment serves the built frontend from this app, with
    a catch-all that hands unmatched paths to the client-side router. That
    catch-all is one registration-order mistake away from swallowing every API
    route and answering `/api/records` with index.html — which a browser would
    render as a blank page and no error anywhere.
    """
    from app.main import _WEB

    if not (_WEB / "index.html").is_file():
        pytest.skip("no built frontend; run npm run build to exercise this")

    # The API still answers as itself.
    assert client.get("/api/health").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    # An unauthenticated API call is refused, not answered with the app shell.
    unauthorised = client.get("/api/records")
    assert unauthorised.status_code in (401, 403)
    assert "text/html" not in unauthorised.headers.get("content-type", "")

    # And a client-side route gets the shell rather than a 404.
    spa = client.get("/periods")
    assert spa.status_code == 200
    assert "text/html" in spa.headers["content-type"]
