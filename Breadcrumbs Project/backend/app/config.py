"""Settings and the five roles the interface is built around."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Breadcrumbs"
    # Development default. Set BREADCRUMBS_SECRET_KEY in any real deployment;
    # the app refuses to start with this value when debug is off.
    secret_key: str = "dev-only-not-a-secret"
    algorithm: str = "HS256"
    token_ttl_minutes: int = 480
    database_url: str = "sqlite:///./breadcrumbs.db"
    ledger_path: str = "./ledger.db"
    # The report specifies 3072. The seed uses a smaller modulus so a cold start
    # is not a minute of prime search; the API reports the real bit length, so a
    # 1024-bit development ceremony says 1024 on screen rather than claiming the
    # production figure.
    anchor_modulus_bits: int = 1024
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]
    debug: bool = True

    model_config = SettingsConfigDict(env_prefix="BREADCRUMBS_")


settings = Settings()

# Which organisation each role signs in as, and where it lands. This mirrors the
# login screen in the design specification exactly.
ROLES: dict[str, dict[str, str]] = {
    "factory": {
        "label": "Factory Compliance Staff",
        "msp_id": "ApexTextileMSP",
        "org": "Apex Textile Ltd",
        "person": "Fatema Begum",
        "identity": "fatema.begum",
        "landing": "/factory/dashboard",
        "summary": "Upload records, manage access grants, view commitment history.",
    },
    "buyer": {
        "label": "Buyer / Brand",
        "msp_id": "PrimarkSourcingMSP",
        "org": "Primark Sourcing Ltd",
        "person": "James Holloway",
        "identity": "james.holloway",
        "landing": "/buyer/portal",
        "summary": "Request specific facts from supplier records and verify them.",
    },
    "auditor": {
        "label": "Auditor",
        "msp_id": "BVCertificationMSP",
        "org": "BV Certification",
        "person": "Dr. Meera Nair",
        "identity": "meera.nair",
        "landing": "/auditor/workspace",
        "summary": "Batch-verify claims and attach signed attestations.",
    },
    "consortium": {
        "label": "Consortium Administrator",
        "msp_id": "BGMEAConsortiumMSP",
        "org": "BGMEA Consortium",
        "person": "Rafiqul Islam",
        "identity": "rafiqul.islam",
        "landing": "/governance",
        "summary": "Approve new members, manage policy proposals, view SLA metrics.",
    },
    "regulator": {
        "label": "Regulator (Observer)",
        "msp_id": "DOLBangladeshMSP",
        "org": "Dept. of Labour, Bangladesh",
        "person": "Lt. Col. (Ret.) Aziz",
        "identity": "aziz",
        "landing": "/regulator",
        "summary": "Read-only view of governance events and aggregate statistics.",
    },
}

# The regulator sees aggregates and governance events, never factory records.
# Enforced in the dependency, not merely in the interface.
READ_ONLY_ROLES = {"regulator"}

# What each role may do, named as capabilities rather than checked ad hoc at
# each handler. A new endpoint has to choose a capability, which makes forgetting
# the check a visible omission rather than a silent one.
#
# Note what the regulator does NOT have: read_records and read_grants. Its screen
# promises it sees no factory data, and this table is where that becomes true.
CAPABILITIES: dict[str, set[str]] = {
    "factory": {
        "read_records", "write_records", "read_grants", "write_grants",
        "read_model", "read_ledger",
        # Seals its own periods; sees whose counter-signature was assigned;
        # reads the accumulator and verifies against it. It may not run an
        # epoch — folding the batch is a consortium act.
        "read_seals", "write_seals", "read_witness", "contribute_seed",
        "read_anchor", "verify_anchor",
    },
    "buyer": {
        "read_records", "read_grants", "write_requests", "verify_records",
        "read_model", "read_ledger",
        # The completeness check is the buyer's instrument, and read_seals is
        # what gates it. Scoping to the periods it holds a grant in is done in
        # scoping.py, not here: this table says what, that module says whose.
        "read_seals", "read_witness", "read_anchor", "verify_anchor",
    },
    "auditor": {
        "read_records", "read_grants", "verify_records", "write_attestations",
        "read_model", "read_ledger",
        "read_seals", "read_witness", "contribute_seed",
        "read_anchor", "verify_anchor",
    },
    "consortium": {
        "read_records", "read_grants", "read_model", "write_model",
        "read_governance", "write_governance", "read_sla", "read_ledger",
        "read_seals", "read_witness", "write_seed_rounds", "contribute_seed",
        "read_anchor", "write_anchor", "verify_anchor",
    },
    "regulator": {
        "read_governance", "read_sla", "read_ledger", "read_model",
        # The accumulator state, its epochs and its digests are consortium-wide
        # facts about the ledger, not factory data, so the observer may read
        # them. It gets no read_seals and no read_witness: both are answers
        # about a named factory's documents.
        "read_anchor",
    },
}
