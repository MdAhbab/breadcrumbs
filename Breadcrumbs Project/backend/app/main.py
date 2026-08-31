"""
Breadcrumbs API.

Serves the five role-scoped views the frontend is designed around, and wraps the
ledger in `model/` without reimplementing any of its rules.

Run:  uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# The model package lives one directory up; it is the system, not a dependency
# of the API, so it is imported rather than vendored.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:  # allows running without an editable install
    sys.path.insert(0, str(_ROOT))

from .config import settings  # noqa: E402
from .db import SessionLocal, init_db  # noqa: E402
from .ledger_service import LedgerError  # noqa: E402
from .routers import auth, governance, ledger, models, records  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.debug and settings.secret_key == "dev-only-not-a-secret":
        raise RuntimeError(
            "BREADCRUMBS_SECRET_KEY is still the development default. "
            "Set a real one before running with debug off."
        )
    init_db()
    from .seed import seed

    session = SessionLocal()
    try:
        result = seed(session)
        print(f"[breadcrumbs] world state: {result['status']}")
    finally:
        session.close()
    yield


app = FastAPI(
    title="Breadcrumbs",
    description=(
        "A permissioned ledger that makes a garment factory's own records provable "
        "without publishing them, and a shared detector whose promotion rule is "
        "enforced on-chain. All data is invented."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LedgerError)
async def ledger_error_handler(request: Request, exc: LedgerError) -> JSONResponse:
    """
    Carry a chaincode refusal up with its reason intact.

    The interface shows the contract's own sentence rather than a generic
    failure, because "grant covers net_pay_bdt, not national_id" tells the user
    what to do and "400 Bad Request" does not.
    """
    return JSONResponse(
        status_code=400, content={"code": exc.code, "message": exc.message}
    )


for router in (auth.router, records.router, models.router, governance.router, ledger.router):
    app.include_router(router, prefix="/api")


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    from .ledger_service import chain_summary

    channels = chain_summary()
    return {
        "status": "ok",
        "channels": channels,
        "ledger_integrity": all(c["integrity_ok"] for c in channels),
        "note": "All data is invented. No real factory, worker or document.",
    }
