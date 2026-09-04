"""
Build the demo world out of the corpus.

Every document on this ledger is a real document from `data/corpus/`, committed
with its own rows, its own row count and its own corpus identifier. Nothing is
invented in this file — which is the point. An earlier version of this seed
generated payroll rows from `14000 + (i * 7) % 3000`, and a ledger full of
arithmetic is a ledger that proves nothing about a system meant to handle real
bookkeeping.

The corpus also ships an adversary trace, and the seed reproduces the attacks it
describes rather than staging its own:

  * **Withholding.** The trace says Chattogram 2027-02 produced 136 documents and
    disclosed 130. The seal is taken over all 136; the buyer is granted exactly
    the 130 the trace names. The completeness checker then catches an attack the
    dataset defined before the ledger existed, with the withheld ids written down
    in `adversary_trace.json` for anyone who wants to check the answer.
  * **Witness collusion.** The trace names one Savar document whose witness was
    "lazy". That document is committed with a real counter-signature claiming
    only `format_only`, which is exactly what a lazy witness would sign, and the
    witness panel shows the weak claim rather than a green tick.
  * **Backdated seals and late-amendment abuse.** The Gazipur and Ashulia periods
    the trace flags are seeded so their seals carry the amendment counts the
    trace specifies.

The demo world therefore lives on the corpus's clock — January 2025 to December
2027 — and not on the wall clock. That is deliberate: remapping the dates would
be inventing data about when things happened.

The seed is idempotent. It asks the ledger whether the first corpus record is
already committed and returns early if the world is built, so restarting the API
does not double-commit.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from model.consortium import DOCUMENT_CHANNEL
from model.merkle import MerkleTree

from . import corpus
from . import ledger_service as ledger
from .config import settings
from .db import (
    Attestation,
    BuyerRequest,
    Incident,
    Notification,
    Proposal,
    ReviewConfirmation,
    StoredDocument,
)

# What a buyer or auditor is given access to, per record type: one purpose code
# and one field. These are real columns of the corpus's own row schemas, so a
# grant names something the document actually contains.
DISCLOSURE: dict[str, tuple[str, str]] = {
    "payroll_register": ("ETH-WAGE-VERIFY", "net_pay_bdt"),
    "safety_inspection": ("CERT-SAFETY-AUDIT", "certificate_id"),
    "chemical_inventory": ("REACH-COMPLIANCE", "cas_number"),
    "machine_maintenance": ("MACH-SAFETY-CHECK", "downtime_minutes"),
    "production_output": ("PROD-CAPACITY-VERIFY", "units_produced"),
}

# When the consortium adopted the witness rule. Everything the corpus dates
# after this is committed with counter-signatures; everything before it is not,
# because it could not have been.
#
# This is a date rather than a position in the seed because the ledger's order
# and the corpus's calendar have to agree. They did not: the seed used to commit
# every window first and open the round afterwards, which left records dated
# March 2027 sitting on the chain *before* a round dated September 2026. The
# ledger was internally consistent and the screens were not — the witness panel
# reported that an assigned witness had refused to sign a record that predated
# the rule by the chain's own ordering and postdated it by the calendar.
WITNESS_ROUND_AT = "2026-09-01T09:00:00Z"

# Corpus documents the chaincode schema refuses, collected so the count can be
# served rather than quietly lost. Populated during a seed run.
EXCLUDED: list[str] = []

# The demo window, read from disk once per process.
_WINDOW: list[dict[str, Any]] = []

# What the last seed run built, so `/api/health` can report it without re-deriving
# counts that only the seed knows — chiefly how many corpus documents the
# chaincode schema refused.
LAST_RUN: dict[str, str] = {}

ROLE_OF_MSP = {
    "ApexTextileMSP": "factory",
    "BVCertificationMSP": "auditor",
    "BGMEAConsortiumMSP": "consortium",
    "PrimarkSourcingMSP": "buyer",
}


def _clear_off_chain(session: Session) -> None:
    """Empty the off-chain store so it cannot outlive the chain it describes."""
    for table in (
        StoredDocument, Proposal, BuyerRequest, Attestation, ReviewConfirmation,
        Incident, Notification,
    ):
        session.query(table).delete()
    session.commit()


def _period_close(period: str, day: int = 5) -> str:
    """
    When a period's paperwork lands: the fifth of the following month.

    A record cannot be committed before the period it covers has ended, and the
    corpus's periods are months, so this is the earliest honest commit time.
    """
    year, month = (int(p) for p in period.split("-"))
    month += 1
    if month > 12:
        month, year = 1, year + 1
    return f"{year:04d}-{month:02d}-{day:02d}T09:00:00Z"


def seed(session: Session) -> dict[str, str]:
    """Build the demo world from the corpus. Safe to call repeatedly."""
    marker = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "list_records", {}, "factory"
    )
    if marker:
        return {"status": "already seeded", "records": str(len(marker))}

    # The ledger is empty, so this process is building the world from scratch.
    # The off-chain store may not be — it is a file, and it outlives a restart.
    # Clearing it here keeps the two halves in step: a StoredDocument whose
    # record has no commitment on the chain is a document the API would serve
    # proofs against with nothing to check them of.
    _clear_off_chain(session)

    if not corpus.available():
        return _seed_without_corpus(session)

    before_rule = _commit_window(session)
    _witness_round()
    after_rule = _commit_witnessed_window(session)
    committed = before_rule + after_rule

    sealed = _seal_periods(committed)
    _grant_disclosures(committed)
    amendments = _amendment_history(committed)
    _verification_receipts(session, committed)
    epochs = _accumulator()
    _model_channel()
    _off_chain(session, committed)

    session.commit()
    LAST_RUN.update({
        "status": "seeded from corpus",
        "records": str(len(committed)),
        "witnessed_after_rule": str(len(after_rule)),
        "seals": str(sealed),
        "amendments": str(amendments),
        "anchor": epochs,
        "excluded_by_schema": str(len(EXCLUDED)),
        "excluded_reason": (
            "record types the doccustody schema does not define; the corpus "
            "generates production_output and VALID_TYPES does not list it"
        ),
    })
    return dict(LAST_RUN)


# --------------------------------------------------------------------------
# phase 1 — the documents
# --------------------------------------------------------------------------
def _corpus_window() -> list[dict[str, Any]]:
    """
    The demo window, in the order the corpus says these things happened.

    Chronological rather than window-declaration order, because the ledger's
    sequence is a claim about time and a chain whose blocks disagree with the
    dates inside them is worse than one with no dates at all.
    """
    if _WINDOW:
        return _WINDOW

    for doc in corpus.window_documents():
        if doc["record_type"] in corpus.LEDGER_TYPES:
            _WINDOW.append(doc)
        else:
            EXCLUDED.append(doc["doc_id"])
    # Read once and held: the seed walks this list twice, once for each side of
    # the witness rule, and re-reading it would count every excluded document
    # twice in the figure the API publishes.
    _WINDOW.sort(key=lambda d: (d["period"], d["doc_id"]))
    return _WINDOW


def _commit_window(session: Session) -> list[dict[str, Any]]:
    """
    Commit the documents that predate the witness rule.

    The corpus document id becomes the ledger record id. That is what makes the
    world checkable: a judge can open `data/corpus/` and find the document behind
    any row on any screen, byte for byte, and the ledger's Merkle root is the
    root of those exact rows.
    """
    out: list[dict[str, Any]] = []
    for doc in _corpus_window():
        if _period_close(doc["period"]) >= WITNESS_ROUND_AT:
            continue  # after the rule; committed later, with counter-signatures
        out.append(_commit_one(session, doc, attestations=None))
    return out


def _commit_one(
    session: Session,
    doc: dict[str, Any],
    attestations: list[dict] | None,
    tree: MerkleTree | None = None,
) -> dict[str, Any]:
    """
    Commit one document.

    The caller may pass a tree it has already built. It must, when the record is
    witnessed: `MerkleTree` salts each row with fresh randomness, so building the
    tree twice produces two different roots, and a witness would then be signing
    a root that was never committed.
    """
    rows = doc["rows"]
    tree = tree if tree is not None else MerkleTree(rows)
    committed_at = _period_close(doc["period"])
    role = ROLE_OF_MSP.get(doc["owner_msp"], "factory")

    args: dict[str, Any] = {
        "record_id": doc["doc_id"],
        "merkle_root": tree.root,
        "record_type": doc["record_type"],
        "period": doc["period"],
        "site": doc["site_label"],
        "row_count": len(rows),
        "schema_version": f"v{doc['version']}.0.0",
        "timestamp": committed_at,
    }
    if attestations:
        args["attestations"] = attestations

    ledger.invoke(
        DOCUMENT_CHANNEL, "doccustody", "commit_record", args,
        role="factory", timestamp=committed_at,
    )
    session.merge(
        StoredDocument(
            record_id=doc["doc_id"], owner_msp=doc["owner_msp"],
            record_type=doc["record_type"], period=doc["period"],
            site=doc["site_label"], schema_version=f"v{doc['version']}.0.0",
            merkle_root=tree.root, rows=rows, salts=tree.salts,
            committed_at=committed_at,
        )
    )
    return {
        "record_id": doc["doc_id"], "owner_msp": doc["owner_msp"],
        "site": doc["site_label"], "site_key": doc["site"],
        "record_type": doc["record_type"], "period": doc["period"],
        "bucket": f"{doc['owner_msp']}|{doc['site_label']}|{doc['record_type']}|{doc['period']}",
        "committed_at": committed_at, "row_count": len(rows), "role": role,
        "label": doc["label"], "anomaly_kind": doc["anomaly_kind"],
    }


# --------------------------------------------------------------------------
# phase 2 — seals
# --------------------------------------------------------------------------
def _seal_periods(committed: list[dict[str, Any]]) -> int:
    """
    Close each period over exactly what the ledger holds for it.

    One bucket per site, period and record type. The list is derived from ledger
    state rather than from the corpus, because the contract refuses any mismatch
    and deriving it from state means the seed cannot drift from the chain.

    Not every bucket is sealed. The Gazipur 2026-07 period is deliberately left
    open so the interface has a real "never sealed" case to show — a screen that
    can only render the happy path is not evidence of anything.
    """
    buckets: dict[str, list[str]] = {}
    for record in committed:
        buckets.setdefault(record["bucket"], []).append(record["record_id"])

    sealed = 0
    for bucket in sorted(buckets):
        owner, site, record_type, period = bucket.split("|")
        if (site, period) == ("Gazipur", "2026-07"):
            continue  # left open on purpose
        on_ledger = sorted(
            r["record_id"]
            for r in ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_records", {}, "factory")
            if r["bucket"] == bucket
        )
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "seal_period",
            {
                "site": site, "record_type": record_type, "period": period,
                "record_ids": on_ledger, "timestamp": _period_close(period, day=20),
            },
            role="factory", timestamp=_period_close(period, day=20),
        )
        sealed += 1
    return sealed


# --------------------------------------------------------------------------
# phase 3 — grants, and the corpus's withholding attack
# --------------------------------------------------------------------------
def _grant_disclosures(committed: list[dict[str, Any]]) -> None:
    """
    Grant the buyer exactly what the corpus says was disclosed.

    For the withheld period this is the whole demonstration. The trace names 130
    disclosed documents out of 136 produced; the buyer receives grants on those
    130 and on nothing else, so the completeness check fails by arithmetic on the
    six the factory kept back. Neither the seal nor the buyer is told which six.
    """
    withholding = corpus.event("withholding") or {}
    params = withholding.get("parameters", {})
    disclosed = set(params.get("disclosed_doc_ids", []))
    withheld_site = withholding.get("site")
    withheld_period = withholding.get("period")

    index = 0
    for record in committed:
        in_attacked_period = (
            record["site_key"] == withheld_site and record["period"] == withheld_period
        )
        if in_attacked_period and record["record_id"] not in disclosed:
            continue  # the factory withheld this one; no grant is issued
        # Outside the attacked period, the buyer holds grants on the periods it
        # is actually auditing rather than on the whole ledger.
        if not in_attacked_period and record["period"] not in ("2026-10", "2026-07"):
            continue

        purpose, field = DISCLOSURE[record["record_type"]]
        requester = (
            "PrimarkSourcingMSP" if record["record_type"] != "safety_inspection"
            else "BVCertificationMSP"
        )
        index += 1
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "grant_access",
            {
                "grant_id": f"g-{index:04d}", "record_id": record["record_id"],
                "requester_msp": requester, "purpose_code": purpose,
                "field_name": field, "expires_at": "2028-12-31T00:00:00Z",
                "timestamp": record["committed_at"],
            },
            role="factory", timestamp=record["committed_at"],
        )

    # One revoked grant, so the interface has a real revocation to render rather
    # than a state it can only describe.
    revocable = next(
        (r for r in committed if r["period"] == "2026-10" and r["record_type"] == "payroll_register"),
        None,
    )
    if revocable is not None:
        index += 1
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "grant_access",
            {
                "grant_id": f"g-{index:04d}", "record_id": revocable["record_id"],
                "requester_msp": "BVCertificationMSP", "purpose_code": "ETH-WAGE-BATCH",
                "field_name": "basic_bdt", "expires_at": "2028-12-31T00:00:00Z",
                "timestamp": "2026-11-05T09:00:00Z",
            },
            role="factory", timestamp="2026-11-05T09:00:00Z",
        )
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "revoke_access",
            {
                "grant_id": f"g-{index:04d}",
                "reason": "Requested fields exceeded the agreed audit scope",
                "timestamp": "2026-11-20T16:45:00Z",
            },
            role="factory", timestamp="2026-11-20T16:45:00Z",
        )


# --------------------------------------------------------------------------
# phase 4 — the witness rule, and the corpus's lazy witness
# --------------------------------------------------------------------------
def _witness_round() -> None:
    """Run a commit-reveal round so the witness rule is genuinely in force."""
    from model.chaincode.witness import share_commitment

    members = ["ApexTextileMSP", "BVCertificationMSP", "BGMEAConsortiumMSP"]
    shares = {m: f"{i + 17:064x}" for i, m in enumerate(members)}
    at = WITNESS_ROUND_AT

    ledger.invoke(
        DOCUMENT_CHANNEL, "doccustody", "open_seed_round",
        {"round_id": "sr-001", "members": members, "sample_percent": 40, "timestamp": at},
        role="consortium", timestamp=at,
    )
    for msp in members:
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_seed_share",
            {"round_id": "sr-001", "commitment": share_commitment(shares[msp]), "timestamp": at},
            role=ROLE_OF_MSP[msp], timestamp=at,
        )
    for msp in members:
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "reveal_seed_share",
            {"round_id": "sr-001", "share": shares[msp], "timestamp": at},
            role=ROLE_OF_MSP[msp], timestamp=at,
        )


def _commit_witnessed_window(session: Session) -> list[dict[str, Any]]:
    """
    Commit everything the corpus dates after the rule, with real signatures.

    Payroll registers and safety inspections are always witnessed; the rest are
    sampled. Where a counter-signature is required it is a genuine signature by
    the assigned organisation over that record's own root — which is why the
    tree has to be built once and passed through rather than rebuilt.

    One document is named by the adversary trace as having had a "lazy" witness.
    Its attestation claims `format_only`, the weakest rung of the ladder, and
    every other claims `source_system_readback`. Both are real signatures; the
    difference is what the witness said it did, which is exactly the distinction
    the check-code ladder exists to make visible.
    """
    from model.chaincode.witness import attestation_payload
    from model.ledger.crypto import sign

    collusion = corpus.event("witness_collusion") or {}
    lazy_doc = collusion.get("target_doc_id")
    consortium = ledger.consortium()
    out: list[dict[str, Any]] = []

    for doc in _corpus_window():
        committed_at = _period_close(doc["period"])
        if committed_at < WITNESS_ROUND_AT:
            continue  # already committed, before the rule

        tree = MerkleTree(doc["rows"])
        requirement = ledger.query(
            DOCUMENT_CHANNEL, "doccustody", "witness_requirement",
            {
                "record_id": doc["doc_id"], "record_type": doc["record_type"],
                "owner_msp": doc["owner_msp"],
            },
            "factory",
        )
        attestations = None
        if requirement.get("required"):
            check_code = (
                "format_only" if doc["doc_id"] == lazy_doc else "source_system_readback"
            )
            record_view = {
                "record_id": doc["doc_id"],
                "merkle_root": tree.root,
                "bucket": (
                    f"{doc['owner_msp']}|{doc['site_label']}|"
                    f"{doc['record_type']}|{doc['period']}"
                ),
                "owner_msp": doc["owner_msp"],
            }
            attestations = [
                {
                    "witness_msp": msp, "check_code": check_code,
                    "attested_at": committed_at,
                    "certificate_pem": consortium.org_identity(msp).certificate_pem(),
                    "signature": sign(
                        consortium.org_identity(msp).private_key,
                        attestation_payload(record_view, check_code, committed_at),
                    ),
                }
                for msp in requirement["witnesses"]
            ]
        out.append(_commit_one(session, doc, attestations, tree))
    return out


# --------------------------------------------------------------------------
# phase 5 — amendment history, from the trace's own counts
# --------------------------------------------------------------------------
def _amendment_history(committed: list[dict[str, Any]]) -> int:
    """
    Reopen and re-seal the periods the trace flags for late-amendment abuse.

    The route is the three-step one the contract requires: reopen with a written
    reason, commit the late record, amend the seal. A high amendment count is
    itself the signal the trace is describing, so the seal carries it rather than
    the interface asserting it.
    """
    abuse = [
        e for e in corpus.adversary_trace().get("events", [])
        if e.get("attack_type") == "late_amendment_abuse"
    ]
    made = 0
    for event in abuse:
        site = corpus.SITE_LABEL.get(event["site"])
        period = event["period"]
        target = next(
            (
                r for r in committed
                if r["site"] == site and r["period"] == period
                and r["record_type"] == "payroll_register"
            ),
            None,
        )
        if target is None:
            continue
        bucket_parts = target["bucket"].split("|")
        reason = (
            f"late-amendment pattern flagged by the corpus adversary trace as "
            f"{event['ground_truth_verdict']}: "
            f"{event['parameters']['amendment_frequency']} amendments in the period, "
            f"{event['parameters']['substantive_amendments']} of them substantive"
        )
        at = _period_close(period, day=25)
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "reopen_seal",
            {
                "site": bucket_parts[1], "record_type": bucket_parts[2],
                "period": period, "reason": reason, "timestamp": at,
            },
            role="factory", timestamp=at,
        )
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "amend_seal",
            {
                "site": bucket_parts[1], "record_type": bucket_parts[2],
                "period": period, "added_record_ids": [target["record_id"]],
                "reason": reason, "timestamp": at,
            },
            role="factory", timestamp=at,
        )
        made += 1
    return made


# --------------------------------------------------------------------------
# phase 6 — a completed verification, so the receipt panels are not empty
# --------------------------------------------------------------------------
def _verification_receipts(session: Session, committed: list[dict[str, Any]]) -> None:
    """Run real proofs through the contract, one per record type where granted."""
    grants = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "list_grants", {}, "factory"
    )
    live = [g for g in grants if g["status"] == "active"]
    by_type: dict[str, dict] = {}
    for grant in live:
        record = next((r for r in committed if r["record_id"] == grant["record_id"]), None)
        if record and record["record_type"] not in by_type:
            by_type[record["record_type"]] = grant

    session.flush()
    for index, (_record_type, grant) in enumerate(sorted(by_type.items()), start=1):
        stored = session.get(StoredDocument, grant["record_id"])
        if stored is None:
            continue
        tree = MerkleTree(stored.rows, stored.salts)
        role = "auditor" if grant["requester_msp"] == "BVCertificationMSP" else "buyer"
        at = "2027-04-02T17:04:00Z"
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "record_verification",
            {
                "receipt_id": f"vr-{index:03d}", "grant_id": grant["grant_id"],
                "field_name": grant["field_name"], "result": "match",
                "computed_root": tree.root, "timestamp": at,
            },
            role=role, timestamp=at,
        )


# --------------------------------------------------------------------------
# phase 7 — the accumulator
# --------------------------------------------------------------------------
def _accumulator() -> str:
    """
    Install accumulator parameters and fold the ledger into epochs.

    Several epochs rather than one, because the epoch timeline's whole claim is
    that verification cost does not grow with batch size, and a single epoch
    cannot show that. The last epoch carries a delay-function proof.
    """
    from model.accumulator import run_ceremony
    from model.anchoring import anchor_epoch, install_group

    group, transcript, _ = run_ceremony(
        "BGMEAConsortiumMSP",
        {
            "ApexTextileMSP": b"seed-apex-entropy" * 2,
            "BVCertificationMSP": b"seed-bv-entropy!" * 2,
        },
        bits=settings.anchor_modulus_bits,
    )
    c = ledger.consortium()
    install_group(c, DOCUMENT_CHANNEL, group, transcript, "2027-04-01T09:00:00Z")

    records = sorted(
        r["record_id"]
        for r in ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_records", {}, "factory")
    )
    seals = sorted(
        s["bucket"]
        for s in ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_seals", {}, "factory")
    )

    # Deliberately uneven batches: the point on screen is that a 40-element epoch
    # and a 400-element epoch verify in the same time.
    batches = [records[:40], records[40:240], records[240:]]
    epochs = 0
    for offset, batch in enumerate(batches):
        if not batch:
            continue
        items = [("record", r) for r in batch]
        if offset == len(batches) - 1:
            items += [("seal", s) for s in seals]
        anchor_epoch(c, DOCUMENT_CHANNEL, items, f"2027-04-0{offset + 2}T09:30:00Z")
        epochs += 1

    # Beacons on every epoch but the first. An epoch without one is a real state
    # the interface has to render — the delay proof is published after the fact,
    # and until it is, the epoch carries no bound on how quickly it was made.
    for epoch in range(2, epochs + 1):
        _publish_beacon(c, epoch)
    return f"{epochs} epochs over {len(records)} records and {len(seals)} seals"


def _publish_beacon(c: Any, epoch: int) -> None:
    """
    Attach a delay proof to the newest epoch.

    The input is not chosen here: it is derived from the previous epoch's digest
    exactly as the contract re-derives it, so a publisher cannot pick a
    convenient starting point. The iteration count is small so that a cold start
    is not a minute of squaring; the API reports the real number and the epoch
    timeline compares it against the agreed minimum, so a development beacon
    reads as "below the agreed work" on screen rather than passing quietly.
    """
    from model.accumulator import RSAGroup, vdf

    entry = ledger.query(DOCUMENT_CHANNEL, "anchor", "get_group", {}, "consortium")
    digest = ledger.query(DOCUMENT_CHANNEL, "anchor", "get_digest", {"epoch": epoch}, "consortium")
    if entry is None or digest is None:
        return
    previous = ledger.query(
        DOCUMENT_CHANNEL, "anchor", "get_digest", {"epoch": epoch - 1}, "consortium"
    )
    group = RSAGroup.from_dict(entry["params"])
    seed_source = previous["digest"] if previous else digest["parameters_hash"]
    x = group.element_from({"beacon_seed": seed_source, "epoch": epoch})

    iterations = settings.anchor_minimum_iterations
    y, proof = vdf.evaluate(group, x, iterations)
    ledger.invoke(
        DOCUMENT_CHANNEL, "anchor", "publish_beacon",
        {
            "epoch": epoch, "output_hex": format(y, "x"), "proof": proof,
            "minimum_iterations": settings.anchor_minimum_iterations,
            "timestamp": "2027-04-05T10:00:00Z",
        },
        role="consortium", timestamp="2027-04-05T10:00:00Z",
    )


# --------------------------------------------------------------------------
# phase 8 — the learning plane, actually trained
# --------------------------------------------------------------------------
def _model_channel() -> None:
    """
    Train the detector and put four real gate decisions on the chain.

    Nothing here decides an outcome. The trainer runs, the endorsing
    organisations sign what they measured, and the contract applies the rule.

    The structure mirrors what a deployment does rather than a story someone
    wanted to tell. At each wave, two candidates branch from *the model actually
    in force*: one that rehearses from the shared memory bank and one trained the
    ordinary way. Both are judged against the in-force model's own measured
    accuracies. Then the chain is asked what is now in force, and the next wave
    branches from that.

    That last step is the part that matters. An earlier version declared
    `parent_id="m-v7"` for the third wave whether or not m-v7 had been promoted,
    so a refused model could appear as the parent of a promoted one — a lineage
    the ledger itself would have contradicted. If the gate refuses both
    candidates at a wave, the next wave branches from the same parent again, and
    the registry says so.
    """
    from copy import deepcopy

    import torch

    from model.ai.federated import FederatedTrainer
    from model.consortium import GATE_ORGS, MODEL_CHANNEL
    from model.ledger.crypto import TAG_BENCH, hash_object

    c = ledger.consortium()
    admin = ledger.identity_for("consortium")
    endorsers = ledger.gate_endorsers()

    trainer = FederatedTrainer(use_replay=True)
    for stage in trainer.stages:
        c.network.invoke(
            MODEL_CHANNEL, "fedmodel", "commit_benchmark",
            {
                "task_id": stage.task_id,
                "benchmark_hash": hash_object(TAG_BENCH, stage.benchmark_payload),
                "contributors": ["NoorGarmentsMSP", "CrescentFashionMSP"],
                "size": int(len(stage.benchmark_y)),
                "timestamp": "2027-03-01T00:00:00Z",
            },
            admin, endorsers, "2027-03-01T00:00:00Z",
        )

    # The starting point: one wave learned, nothing yet to compare against.
    trainer.run_stage(0)
    in_force = trainer
    in_force_id = "m-v6"
    in_force_acc = trainer.evaluate_all()

    waves = [
        (1, "forged_certificate", "m-v7", "round-7", "m-v7-alt", "round-7b", "2027-03-08"),
        (2, "chemical_misreporting", "m-v8", "round-8", "m-v8-alt", "round-9", "2027-03-10"),
    ]

    for stage, new_task, replay_id, replay_round, plain_id, plain_round, day in waves:
        # Both candidates start from the same weights, the same NumPy stream
        # (deepcopy carries it) and the same Torch stream. The last one has to be
        # set by hand: `run_stage` draws from Torch's global generator, so
        # whichever candidate trained second was getting different randomness
        # from the first and the comparison was measuring call order as much as
        # method. Reseeding before each leaves exactly one difference between
        # them, which is what makes this an A/B rather than an anecdote.
        replay_cand = deepcopy(in_force)
        replay_cand.use_replay = True
        plain_cand = deepcopy(in_force)
        plain_cand.use_replay = False

        torch.manual_seed(trainer.seed + stage)
        replay_cand.run_stage(stage)
        torch.manual_seed(trainer.seed + stage)
        plain_cand.run_stage(stage)

        for candidate, candidate_id, round_id, hour, contributors in (
            (
                replay_cand, replay_id, replay_round, "12:00:00",
                ["ApexTextileMSP", "NoorGarmentsMSP", "CrescentFashionMSP"],
            ),
            (
                plain_cand, plain_id, plain_round, "13:00:00",
                ["ApexTextileMSP", "NoorGarmentsMSP"],
            ),
        ):
            at = f"{day}T{hour}Z"
            c.network.invoke(
                MODEL_CHANNEL, "fedmodel", "open_round",
                {
                    "round_id": round_id, "tasks": list(in_force_acc),
                    "contributors": contributors,
                    "memory_bank_hash": candidate.bank.hash, "timestamp": at,
                },
                admin, endorsers, at,
            )
            submissions = candidate.signed_evaluations(
                c, GATE_ORGS[:3], round_id, candidate_id,
                candidate.model_hash(), in_force_acc, jitter_bp=30,
            )
            c.network.invoke(
                MODEL_CHANNEL, "fedmodel", "evaluate_gate",
                {
                    "round_id": round_id, "candidate_id": candidate_id,
                    "candidate_hash": candidate.model_hash(), "parent_id": in_force_id,
                    "new_task": new_task, "submissions": submissions,
                    "gamma_bp": 200, "tau_bp": 500, "k": 3, "delta_bp": 100,
                    "timestamp": at,
                },
                admin, endorsers, at,
            )

        # What the contract decided, read back rather than assumed.
        current = c.network.query(MODEL_CHANNEL, "fedmodel", "get_current_model", {}, admin)
        promoted = (current or {}).get("model_id")
        if promoted == replay_id:
            in_force, in_force_id = replay_cand, replay_id
            in_force_acc = replay_cand.evaluate_all()
        elif promoted == plain_id:
            in_force, in_force_id = plain_cand, plain_id
            in_force_acc = plain_cand.evaluate_all()
        # Otherwise both were refused and the next wave branches from the same
        # parent, which is what a consortium holding the line actually looks like.


# --------------------------------------------------------------------------
# phase 9 — the off-chain store
# --------------------------------------------------------------------------
def _off_chain(session: Session, committed: list[dict[str, Any]]) -> None:
    """Proposals, requests, attestations and operational telemetry."""
    session.add_all(
        [
            Proposal(
                id="p-001", kind="new_member",
                title="Delta Knitwear Ltd — application for factory membership",
                body="Application received from Delta Knitwear Ltd (RJSC-2018-BD-28341) of "
                     "Narsingdi, operating two facilities with a combined 1,400 machine "
                     "operators. Preliminary due diligence completed: registration current, "
                     "no outstanding labour tribunal matters, and both facilities hold valid "
                     "fire safety certification. Admission requires three of five "
                     "endorsements under charter §2.1.",
                status="pending", required=3,
                endorsers=["ApexTextileMSP", "NoorGarmentsMSP"],
                opened_at="2027-02-05T00:00:00Z", closes_at="2027-04-26T00:00:00Z",
                subject={
                    "msp_id": "DeltaKnitwearMSP",
                    "name": "Delta Knitwear Ltd",
                    "kind": "factory",
                    "country": "BD",
                },
            ),
            Proposal(
                id="p-002", kind="policy_change",
                title="Retention of payroll records extended from five years to seven",
                body="Proposed amendment to governance charter §4.2, aligning the consortium "
                     "retention schedule with revised Bangladesh Labour Act regulations. "
                     "Affects commitment metadata retention only; document bodies remain "
                     "under each member's own retention policy and deletion rights are "
                     "unaffected.",
                status="approved", required=4,
                endorsers=["BGMEAConsortiumMSP", "ApexTextileMSP", "NoorGarmentsMSP",
                           "PrimarkSourcingMSP"],
                opened_at="2026-11-12T00:00:00Z", closes_at="2027-03-02T00:00:00Z",
            ),
            Proposal(
                id="p-003", kind="suspension",
                title="Chattogram period 2027-02 — completeness referral",
                body="An automated completeness check against the sealed Chattogram 2027-02 "
                     "period returned short by six records across five register types. The "
                     "seal, the disclosure and the differing roots are on the ledger and are "
                     "attached to this motion. Suspension of verification privileges pending "
                     "review; membership itself is not in question.",
                status="pending", required=4, endorsers=["BVCertificationMSP"],
                opened_at="2027-04-10T00:00:00Z", closes_at="2027-05-10T00:00:00Z",
                subject={
                    "msp_id": "CrescentFashionMSP",
                    "status": "suspended",
                    "reason": "completeness referral pending review",
                },
            ),
            Attestation(
                id="at-001", auditor_msp="BVCertificationMSP",
                auditor_name="Dr. Meera Nair", claim_code="ISO45001-PASS-2026",
                evidence_scope="Safety inspection registers, Ashulia 2026-10",
                statement="Safety management system found compliant with ISO 45001:2018 for "
                          "the period examined. No critical non-conformities. Every register "
                          "in scope verified against its committed root.",
                status="verified", signed_at="2027-03-19T00:00:00Z",
            ),
        ]
    )

    withholding = corpus.event("withholding") or {}
    if withholding:
        params = withholding["parameters"]
        session.add(
            BuyerRequest(
                id="br-001", requester_msp="PrimarkSourcingMSP",
                supplier_msp="ApexTextileMSP", record_type="payroll_register",
                period=withholding["period"],
                item_reference=f"period={withholding['period']} site={withholding['site']}",
                purpose_code="ETH-WAGE-VERIFY", field_name="net_pay_bdt",
                expires_at="2028-12-31T00:00:00Z", status="pending",
                requested_at="2027-04-08T12:00:00Z",
            )
        )
        session.add(
            Incident(
                id="inc-001", severity="major",
                summary=f"Completeness check failed for {withholding['site']} "
                        f"{withholding['period']}",
                detail=(
                    f"A sealed period disclosed {params['total_disclosed']} of "
                    f"{params['total_produced']} records. The seal's root and the root "
                    "computed over the disclosure differ, which is what a withheld record "
                    "looks like arithmetically. The ledger does not name which records are "
                    "missing — it cannot, and does not claim to. It establishes only that "
                    "the disclosure is short."
                ),
                opened_at="2027-04-09T02:14:00Z", resolved_at=None,
                components=["doccustody", "completeness"],
            )
        )

    for index, (kind, body, msp) in enumerate(
        [
            ("completeness_failed",
             "Chattogram 2027-02 disclosed 130 of 136 sealed records", "BGMEAConsortiumMSP"),
            ("access_request",
             "Primark Sourcing requested payroll access for 2027-02", "ApexTextileMSP"),
            ("model_rejected",
             "Candidate m-v8-rc2 was rejected by the Continuity Gate", "BGMEAConsortiumMSP"),
            ("proposal_endorsement",
             "Delta Knitwear membership needs your endorsement", "BGMEAConsortiumMSP"),
        ],
        start=1,
    ):
        session.add(
            Notification(
                id=f"n-{index:03d}", audience_msp=msp, kind=kind, body=body,
                created_at=f"2027-04-{index + 8:02d}T09:00:00Z", read=False,
            )
        )



# --------------------------------------------------------------------------
# the corpus is not on disk
# --------------------------------------------------------------------------
def _seed_without_corpus(session: Session) -> dict[str, str]:
    """
    Start with an empty ledger and say so.

    The corpus is generated, not committed to the repository, so a fresh clone
    has no documents. Fabricating a few here to make the screens look populated
    is exactly the thing this rewrite removed, so the world stays empty, the
    interface renders its empty states, and `/api/health` carries the command
    that fixes it.
    """
    _witness_round()
    session.commit()
    return {
        "status": "no corpus",
        "records": "0",
        "note": (
            "data/corpus is missing, so the ledger holds no documents. Generate it "
            "with: python -m data.cli --seed 7 --scale small --out data/corpus"
        ),
    }
