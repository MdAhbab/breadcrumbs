"""
Seed data.

Every value here matches the frontend design specification, so the interface
lights up with the same organisations, purpose codes and record identifiers the
screens were drawn around. That consistency is what makes a demo feel like a
product rather than a set of forms.

The seed is idempotent: it checks the ledger for rc-001 and returns early if the
world is already built, so restarting the API does not double-commit.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from model.consortium import DOCUMENT_CHANNEL
from model.merkle import MerkleTree

from . import ledger_service as ledger
from .config import settings
from .db import (
    Attestation,
    BuyerRequest,
    Incident,
    Notification,
    Proposal,
    SlaPoint,
    StoredDocument,
)

RECORDS = [
    # record_id, type, period, site, rows, schema, committed
    ("rc-001", "payroll_register", "2026-07", "Gazipur", 1847, "v2.1.0", "2026-08-05T09:14:00Z"),
    ("rc-002", "safety_inspection", "2026-Q2", "Gazipur", 3, "v2.1.0", "2026-07-02T10:00:00Z"),
    ("rc-003", "payroll_register", "2026-06", "Gazipur", 1823, "v2.0.3", "2026-07-04T09:00:00Z"),
    ("rc-004", "chemical_inventory", "2026-08", "Ashulia", 64, "v2.1.0", "2026-08-12T14:20:00Z"),
    ("rc-005", "machine_maintenance", "2026-07", "Ashulia", 128, "v2.1.0", "2026-08-01T11:45:00Z"),
]

GRANTS = [
    # grant_id, record, requester, purpose, field, expires, then action
    ("g-001", "rc-001", "PrimarkSourcingMSP", "ETH-WAGE-VERIFY", "net_pay_bdt", "2026-09-30T00:00:00Z", None),
    ("g-002", "rc-002", "BVCertificationMSP", "CERT-SAFETY-AUDIT", "certificate_id", "2026-10-15T00:00:00Z", None),
    ("g-003", "rc-003", "BVCertificationMSP", "ETH-WAGE-VERIFY", "net_pay_bdt", "2026-07-31T00:00:00Z", None),
    ("g-004", "rc-001", "BVCertificationMSP", "ETH-WAGE-BATCH", "net_pay_bdt", "2026-12-31T00:00:00Z", "revoke"),
]


def _payroll_rows(n: int) -> list[dict]:
    return [
        {"worker_ref": f"W-{i:05d}", "net_pay_bdt": 14000 + (i * 7) % 3000}
        for i in range(n)
    ]


def seed(session: Session) -> dict[str, str]:
    """Build the demo world. Safe to call repeatedly."""
    existing = ledger.query(
        DOCUMENT_CHANNEL, "doccustody", "get_record", {"record_id": "rc-001"}, "factory"
    )
    if existing is not None:
        return {"status": "already seeded"}

    trees: dict[str, MerkleTree] = {}
    for record_id, rtype, period, site, n_rows, schema, committed in RECORDS:
        rows = _payroll_rows(n_rows)
        tree = MerkleTree(rows)
        trees[record_id] = tree
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_record",
            {
                "record_id": record_id, "merkle_root": tree.root, "record_type": rtype,
                "period": period, "site": site, "row_count": n_rows,
                "schema_version": schema, "timestamp": committed,
            },
            role="factory", timestamp=committed,
        )
        session.merge(
            StoredDocument(
                record_id=record_id, owner_msp="ApexTextileMSP", record_type=rtype,
                period=period, site=site, schema_version=schema,
                merkle_root=tree.root, rows=rows, salts=tree.salts, committed_at=committed,
            )
        )

    # rc-003 was corrected by rc-001's period; mark the supersession on-chain.
    ledger.invoke(
        DOCUMENT_CHANNEL, "doccustody", "supersede_record",
        {
            "record_id": "rc-003", "new_record_id": "rc-001",
            "reason": "June register reissued after overtime recalculation",
            "timestamp": "2026-08-05T09:20:00Z",
        },
        role="factory", timestamp="2026-08-05T09:20:00Z",
    )

    for grant_id, record_id, requester, purpose, field, expires, action in GRANTS:
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "grant_access",
            {
                "grant_id": grant_id, "record_id": record_id, "requester_msp": requester,
                "purpose_code": purpose, "field_name": field, "expires_at": expires,
                "timestamp": "2026-08-06T09:00:00Z",
            },
            role="factory", timestamp="2026-08-06T09:00:00Z",
        )
        if action == "revoke":
            ledger.invoke(
                DOCUMENT_CHANNEL, "doccustody", "revoke_access",
                {
                    "grant_id": grant_id,
                    "reason": "Requested fields exceeded the agreed audit scope",
                    "timestamp": "2026-08-22T16:45:00Z",
                },
                role="factory", timestamp="2026-08-22T16:45:00Z",
            )

    # A completed verification, so the receipt panel is not empty. The tree is
    # taken from the loop above rather than re-read: the session has not flushed
    # yet, so a lookup here would find nothing.
    tree = trees["rc-001"]
    ledger.invoke(
        DOCUMENT_CHANNEL, "doccustody", "record_verification",
        {
            "receipt_id": "vr-001", "grant_id": "g-001", "field_name": "net_pay_bdt",
            "result": "match", "computed_root": tree.root,
            "timestamp": "2026-08-22T17:04:00Z",
        },
        role="buyer", timestamp="2026-08-22T17:04:00Z",
    )

    session.add_all(
        [
            Proposal(
                id="p-001", kind="new_member",
                title="Delta Knitwear Ltd — New Factory Member",
                body="Application from Delta Knitwear Ltd (RJSC-2018-BD-28341), Narsingdi. "
                     "Passed preliminary due-diligence. 3-of-5 endorsement required.",
                status="pending", required=3,
                endorsers=["ApexTextileMSP", "NoorGarmentsMSP"],
                opened_at="2026-08-05T00:00:00Z", closes_at="2026-09-26T00:00:00Z",
            ),
            Proposal(
                id="p-002", kind="policy_change",
                title="Update retention policy: payroll records from 5 to 7 years",
                body="Proposed amendment to governance charter §4.2 to align with revised "
                     "Bangladesh Labour Act regulations effective January 2027.",
                status="approved", required=4,
                endorsers=["BGMEAConsortiumMSP", "ApexTextileMSP", "NoorGarmentsMSP",
                           "PrimarkSourcingMSP"],
                opened_at="2026-05-12T00:00:00Z", closes_at="2026-09-02T00:00:00Z",
            ),
            Proposal(
                id="p-003", kind="suspension",
                title="Crescent Fashion Ltd — Suspension Review",
                body="Repeated failure to serve verification proofs within the agreed "
                     "window. Suspension pending review.",
                status="pending", required=4, endorsers=["BVCertificationMSP"],
                opened_at="2026-08-22T00:00:00Z", closes_at="2026-09-21T00:00:00Z",
            ),
            BuyerRequest(
                id="br-001", requester_msp="PrimarkSourcingMSP",
                supplier_msp="NoorGarmentsMSP", record_type="chemical_inventory",
                period="2026-08", item_reference="batch_id=NG-2026-08-114",
                purpose_code="REACH-COMPLIANCE", field_name="svhc_ppm",
                expires_at="2026-10-31T00:00:00Z", status="pending",
                requested_at="2026-08-20T12:00:00Z",
            ),
            Attestation(
                id="at-001", auditor_msp="BVCertificationMSP", auditor_name="Dr. Meera Nair",
                claim_code="ISO45001-PASS-Q2-2026", evidence_scope="All records in this batch",
                statement="Safety management system found compliant with ISO 45001:2018 "
                          "for Q2 2026. No critical non-conformities.",
                status="verified", signed_at="2026-08-19T00:00:00Z",
            ),
            Incident(
                id="inc-001", severity="minor",
                summary="Ordering service leader election during host patching",
                detail="orderer0 was restarted for a kernel patch. A new leader was elected "
                       "in 4.2 seconds. Two verification requests were retried by the client "
                       "and succeeded. No transactions were lost and no data was affected.",
                opened_at="2026-08-11T02:14:00Z", resolved_at="2026-08-11T02:19:00Z",
                components=["ordering-service"],
            ),
        ]
    )

    # A month of SLA points, with the dip on the 11th matching the incident.
    for day in range(1, 31):
        dipped = day == 11
        session.add(
            SlaPoint(
                day=f"2026-08-{day:02d}",
                uptime_pct="97.42" if dipped else "100.00",
                verifications=28 + (day * 13) % 61,
                avg_response_ms=340 if dipped else 150 + (day * 7) % 45,
            )
        )

    for i, (kind, body, msp) in enumerate(
        [
            ("access_request", "Noor Garments Ltd requested chemical inventory access",
             "ApexTextileMSP"),
            ("grant_expiring", "Primark Sourcing grant on rc-004 expires in 1 day",
             "ApexTextileMSP"),
            ("model_rejected", "Candidate m-v8-rc2 was rejected by the Continuity Gate",
             "BGMEAConsortiumMSP"),
            ("proposal_endorsement", "Delta Knitwear membership needs your endorsement",
             "BGMEAConsortiumMSP"),
        ],
        start=1,
    ):
        session.add(
            Notification(
                id=f"n-{i:03d}", audience_msp=msp, kind=kind, body=body,
                created_at=f"2026-08-{20 + i:02d}T09:00:00Z", read=False,
            )
        )

    _seed_period_seal(session)
    _seed_witness_round()
    anchor_note = _seed_accumulator()

    session.commit()
    return {
        "status": "seeded",
        "records": str(len(RECORDS) + len(SEALED_BUCKET_RECORDS)),
        "anchor": anchor_note,
    }


# --------------------------------------------------------------------------
# the four mechanisms, so their screens have something true to show
# --------------------------------------------------------------------------
# Five registers in one period, of which the buyer is granted four. That gap is
# the completeness demonstration: the seal says five, the disclosure carries
# four, and the arithmetic — not anybody's word — is what catches it.
SEALED_BUCKET_RECORDS = [
    ("rc-071", 1204, "2026-06-30T09:00:00Z"),
    ("rc-072", 1198, "2026-06-30T09:05:00Z"),
    ("rc-073", 1211, "2026-06-30T09:10:00Z"),
    ("rc-074", 1190, "2026-06-30T09:15:00Z"),
    ("rc-075", 1207, "2026-06-30T09:20:00Z"),
]
SEALED_SITE = "Narayanganj"
SEALED_TYPE = "payroll_register"
SEALED_PERIOD = "2026-05"
SEALED_BUCKET = f"ApexTextileMSP|{SEALED_SITE}|{SEALED_TYPE}|{SEALED_PERIOD}"


def _seed_period_seal(session: Session) -> None:
    """Commit five registers, seal the period over exactly them, disclose four."""
    for record_id, n_rows, committed in SEALED_BUCKET_RECORDS:
        rows = _payroll_rows(n_rows)
        tree = MerkleTree(rows)
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_record",
            {
                "record_id": record_id, "merkle_root": tree.root,
                "record_type": SEALED_TYPE, "period": SEALED_PERIOD, "site": SEALED_SITE,
                "row_count": n_rows, "schema_version": "v2.1.0", "timestamp": committed,
            },
            role="factory", timestamp=committed,
        )
        session.merge(
            StoredDocument(
                record_id=record_id, owner_msp="ApexTextileMSP", record_type=SEALED_TYPE,
                period=SEALED_PERIOD, site=SEALED_SITE, schema_version="v2.1.0",
                merkle_root=tree.root, rows=rows, salts=tree.salts, committed_at=committed,
            )
        )

    # Seal over what the ledger actually holds, not over the literal above: the
    # contract refuses any mismatch, and deriving the list from state means this
    # cannot drift if the fixtures change.
    on_ledger = sorted(
        r["record_id"]
        for r in ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_records", {}, "factory")
        if r["bucket"] == SEALED_BUCKET
    )
    ledger.invoke(
        DOCUMENT_CHANNEL, "doccustody", "seal_period",
        {
            "site": SEALED_SITE, "record_type": SEALED_TYPE, "period": SEALED_PERIOD,
            "record_ids": on_ledger, "timestamp": "2026-07-01T10:00:00Z",
        },
        role="factory", timestamp="2026-07-01T10:00:00Z",
    )

    # Four of the five. The fifth is withheld, which is the whole point.
    for i, record_id in enumerate(on_ledger[:4], start=10):
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "grant_access",
            {
                "grant_id": f"g-{i:03d}", "record_id": record_id,
                "requester_msp": "PrimarkSourcingMSP", "purpose_code": "ETH-WAGE-VERIFY",
                "field_name": "net_pay_bdt", "expires_at": "2026-12-31T00:00:00Z",
                "timestamp": "2026-07-02T09:00:00Z",
            },
            role="factory", timestamp="2026-07-02T09:00:00Z",
        )

    # A genuinely late record, brought in through the three-step route: reopen the
    # period with a reason, commit, re-seal. The history panel therefore shows a
    # real amendment rather than a re-declaration of a record the bucket already
    # held — which is what this seed used to do, because an earlier version of the
    # contract had no route for a late record at all. It has one now.
    reason = "night-shift register arrived after the Narayanganj line reconciliation"
    ledger.invoke(
        DOCUMENT_CHANNEL, "doccustody", "reopen_seal",
        {
            "site": SEALED_SITE, "record_type": SEALED_TYPE, "period": SEALED_PERIOD,
            "reason": reason, "timestamp": "2026-07-03T09:00:00Z",
        },
        role="factory", timestamp="2026-07-03T09:00:00Z",
    )

    late_rows = _payroll_rows(612)
    late_tree = MerkleTree(late_rows)
    ledger.invoke(
        DOCUMENT_CHANNEL, "doccustody", "commit_record",
        {
            "record_id": "rc-nar-late", "merkle_root": late_tree.root,
            "record_type": SEALED_TYPE, "period": SEALED_PERIOD, "site": SEALED_SITE,
            "row_count": 612, "schema_version": "v2.1.0",
            "timestamp": "2026-07-03T10:00:00Z",
        },
        role="factory", timestamp="2026-07-03T10:00:00Z",
    )
    session.merge(
        StoredDocument(
            record_id="rc-nar-late", owner_msp="ApexTextileMSP", record_type=SEALED_TYPE,
            period=SEALED_PERIOD, site=SEALED_SITE, schema_version="v2.1.0",
            merkle_root=late_tree.root, rows=late_rows, salts=late_tree.salts,
            committed_at="2026-07-03T10:00:00Z",
        )
    )

    ledger.invoke(
        DOCUMENT_CHANNEL, "doccustody", "amend_seal",
        {
            "site": SEALED_SITE, "record_type": SEALED_TYPE, "period": SEALED_PERIOD,
            "added_record_ids": ["rc-nar-late"],
            "reason": reason,
            "timestamp": "2026-07-03T11:00:00Z",
        },
        role="factory", timestamp="2026-07-03T11:00:00Z",
    )

    session.flush()


def _seed_witness_round() -> None:
    """Run a commit-reveal round so the witness rule is actually in force."""
    from model.chaincode.witness import share_commitment

    members = ["ApexTextileMSP", "BVCertificationMSP", "BGMEAConsortiumMSP"]
    role_of = {
        "ApexTextileMSP": "factory",
        "BVCertificationMSP": "auditor",
        "BGMEAConsortiumMSP": "consortium",
    }
    shares = {m: f"{i + 17:064x}" for i, m in enumerate(members)}

    ledger.invoke(
        DOCUMENT_CHANNEL, "doccustody", "open_seed_round",
        {
            "round_id": "sr-001", "members": members, "sample_percent": 40,
            "timestamp": "2026-07-05T09:00:00Z",
        },
        role="consortium", timestamp="2026-07-05T09:00:00Z",
    )
    for msp in members:
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "commit_seed_share",
            {
                "round_id": "sr-001", "commitment": share_commitment(shares[msp]),
                "timestamp": "2026-07-05T09:10:00Z",
            },
            role=role_of[msp], timestamp="2026-07-05T09:10:00Z",
        )
    for msp in members:
        ledger.invoke(
            DOCUMENT_CHANNEL, "doccustody", "reveal_seed_share",
            {
                "round_id": "sr-001", "share": shares[msp],
                "timestamp": "2026-07-05T09:20:00Z",
            },
            role=role_of[msp], timestamp="2026-07-05T09:20:00Z",
        )


def _seed_accumulator() -> str:
    """
    Install accumulator parameters, fold one epoch, and attach a delay proof.

    The dev seed uses a small modulus so a cold start is not a minute of prime
    search. That is a development convenience and the API reports the real bit
    length, so the screen says 1024 when it is 1024 rather than the 3072 the
    report specifies.
    """
    from model.accumulator import run_ceremony
    from model.anchoring import anchor_epoch, install_group

    group, transcript, _ = run_ceremony(
        "BGMEAConsortiumMSP",
        {"ApexTextileMSP": b"seed-apex-entropy" * 2, "BVCertificationMSP": b"seed-bv-entropy!" * 2},
        bits=settings.anchor_modulus_bits,
    )
    c = ledger.consortium()
    install_group(c, DOCUMENT_CHANNEL, group, transcript, "2026-07-06T09:00:00Z")

    records = [
        r["record_id"]
        for r in ledger.query(DOCUMENT_CHANNEL, "doccustody", "list_records", {}, "factory")
    ]
    items = [("record", r) for r in sorted(records)] + [("seal", SEALED_BUCKET)]
    anchor_epoch(c, DOCUMENT_CHANNEL, items, "2026-07-06T09:30:00Z")
    return f"epoch 1 over {len(items)} elements, {settings.anchor_modulus_bits}-bit modulus"
