"""Settings and the five roles the interface is built around."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Breadcrumbs"
    # Development default. Set BREADCRUMBS_SECRET_KEY in any real deployment;
    # the app refuses to start with this value when debug is off.
    secret_key: str = "dev-only-not-a-secret"
    algorithm: str = "HS256"
    token_ttl_minutes: int = 480
    database_url: str = "sqlite:///./breadcrumbs.db"
    ledger_path: str = "./ledger.db"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]
    debug: bool = True

    class Config:
        env_prefix = "BREADCRUMBS_"


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
