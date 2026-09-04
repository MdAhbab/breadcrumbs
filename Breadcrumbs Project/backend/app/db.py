"""
The off-chain store.

The split between this file and the ledger is the report's Table 2, made
concrete. What lives here: document bodies, row salts, proposal text, incident
notes, notifications. What lives on the ledger: root hashes, metadata, grants,
model decisions.

Nothing personal is on the chain, and everything here is deletable — which is
the point. A right to erasure and an append-only ledger cannot both hold for the
same bytes, so the bytes that must be erasable never go on the ledger.

In a deployment this store sits inside the factory and holds ciphertext. Here it
holds plaintext in SQLite so the demo can show a proof being built, and that
difference is worth naming rather than glossing.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import JSON, Boolean, Column, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

engine = create_engine(
    settings.database_url, connect_args={"check_same_thread": False}, future=True
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


class StoredDocument(Base):
    """
    A document body, kept off-chain.

    `salts` is the reason a proof can disclose one row without exposing the
    others: each row was hashed with its own salt, and only the salt for the
    disclosed row is ever released.
    """

    __tablename__ = "documents"

    record_id = Column(String, primary_key=True)
    owner_msp = Column(String, nullable=False, index=True)
    record_type = Column(String, nullable=False)
    period = Column(String, nullable=False)
    site = Column(String, nullable=False)
    schema_version = Column(String, nullable=False)
    merkle_root = Column(String, nullable=False)
    rows = Column(JSON, nullable=False)
    salts = Column(JSON, nullable=False)
    committed_at = Column(String, nullable=False)


class Proposal(Base):
    """
    A governance proposal, and what it does to the ledger if it carries.

    `subject` is what makes a motion more than a note. An admission motion names
    the organisation it admits and a suspension names the member it suspends, so
    that reaching the threshold can be executed rather than merely displayed.
    Without it, three members could endorse "admit Delta Knitwear", the motion
    would go green, and Delta Knitwear would exist nowhere.
    """

    __tablename__ = "proposals"

    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False)  # new_member | policy_change | suspension
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")
    required = Column(Integer, nullable=False)
    endorsers = Column(JSON, nullable=False, default=list)
    opened_at = Column(String, nullable=False)
    closes_at = Column(String, nullable=False)
    # {"msp_id", "name", "kind", "country"} for an admission;
    # {"msp_id", "status", "reason"} for a suspension; null for a policy change.
    subject = Column(JSON, nullable=True)
    # Set once the motion has been carried out on the ledger, so a restart or a
    # second endorsement cannot execute it twice.
    executed_tx = Column(String, nullable=True)


class BuyerRequest(Base):
    """A buyer's narrow-scope request, before it becomes an on-chain grant."""

    __tablename__ = "buyer_requests"

    id = Column(String, primary_key=True)
    requester_msp = Column(String, nullable=False, index=True)
    supplier_msp = Column(String, nullable=False)
    record_type = Column(String, nullable=False)
    period = Column(String, nullable=False)
    item_reference = Column(String, nullable=True)
    purpose_code = Column(String, nullable=False)
    field_name = Column(String, nullable=False)
    expires_at = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    grant_id = Column(String, nullable=True)
    requested_at = Column(String, nullable=False)
    # Why it was declined, in the factory's own words. The endpoint used to
    # accept a reason, parse it and drop it, so a buyer was told a request had
    # been refused and never told why.
    decline_reason = Column(String, nullable=True)
    # Several columns asked for in one go share a batch, so the factory sees
    # "Primark wants four things from this register" rather than four unrelated
    # rows it has to notice are related.
    batch_id = Column(String, nullable=True, index=True)


class Attestation(Base):
    """An auditor's signed statement over a batch of verifications."""

    __tablename__ = "attestations"

    id = Column(String, primary_key=True)
    auditor_msp = Column(String, nullable=False)
    auditor_name = Column(String, nullable=False)
    claim_code = Column(String, nullable=False)
    evidence_scope = Column(String, nullable=False)
    statement = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="verified")
    signed_at = Column(String, nullable=False)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True)
    severity = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    detail = Column(Text, nullable=False)
    opened_at = Column(String, nullable=False)
    resolved_at = Column(String, nullable=True)
    components = Column(JSON, nullable=False, default=list)


class SlaPoint(Base):
    __tablename__ = "sla_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day = Column(String, nullable=False, index=True)
    uptime_pct = Column(String, nullable=False)
    verifications = Column(Integer, nullable=False)
    avg_response_ms = Column(Integer, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True)
    audience_msp = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False)
    body = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    read = Column(Boolean, nullable=False, default=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """
    Bring an existing SQLite file up to the current model.

    `create_all` creates missing *tables* and never touches a table that already
    exists, so a column added to a model after somebody has run the app leaves
    them with a database the code cannot query — on a laptop being used to
    demonstrate the product, at the worst possible moment. Every table here is
    emptied and rebuilt by the seed on each boot, so this is only ever adding a
    column to something with no rows worth keeping.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            present = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                kind = column.type.compile(engine.dialect)
                connection.execute(
                    text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {kind}")
                )


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def as_dict(row: Any) -> dict[str, Any]:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def notify(session: Session, audience_msp: str, kind: str, body: str) -> Notification:
    """
    Tell one organisation that something happened to it.

    Off-chain on purpose, and deliberately thin: a notification is a pointer at
    somewhere else in the product, never the record of the thing itself. The
    thing itself is the grant, the revocation or the request, and those live
    where they belong.

    The seed ships four of these, so the bell in the sidebar existed and was
    only ever showing history. A request made through the running app wrote
    none, which meant the one event in this system that requires a human being
    to do something was the one event nobody was told about.
    """
    import datetime as dt

    row = Notification(
        id=f"n-{session.query(Notification).count() + 1:03d}",
        audience_msp=audience_msp,
        kind=kind,
        body=body,
        created_at=dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        read=False,
    )
    session.add(row)
    return row
