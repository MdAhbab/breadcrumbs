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

from . import world  # noqa: E402
from .config import settings  # noqa: E402
from .db import SessionLocal, init_db  # noqa: E402
from .ledger_service import LedgerError  # noqa: E402
from .routers import (  # noqa: E402
    anchor,
    auth,
    governance,
    ledger,
    models,
    records,
    seals,
    witness,
    workspace,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.debug and settings.secret_key == "dev-only-not-a-secret":
        raise RuntimeError(
            "BREADCRUMBS_SECRET_KEY is still the development default. "
            "Set a real one before running with debug off."
        )
    init_db()
    # Built on a background thread so the socket opens immediately. See world.py
    # for why: the seed is forty seconds of genuine work, and a process manager
    # that waits for it concludes the app failed to start.
    world.start(SessionLocal)
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

# Paths that mean something before the world exists: the health check that
# reports the build, the sign-in that needs no ledger, and the docs.
_ALWAYS_OPEN = ("/api/health", "/api/auth/", "/docs", "/openapi.json", "/redoc")


@app.middleware("http")
async def hold_until_built(request: Request, call_next):
    """
    Refuse data requests while the world is being built, and say so.

    Serving empty lists would be worse than refusing: an empty list is a claim
    that there is nothing, and during a cold start that claim is false. A 503
    with the reason lets every screen say "still building, about 20s left"
    using the same error path it already has for a refusal.
    """
    path = request.url.path
    if path.startswith("/api/") and not path.startswith(_ALWAYS_OPEN):
        if world.failed():
            return JSONResponse(
                status_code=503,
                content={"code": "WORLD_FAILED", "message": world.waiting_message()},
            )
        if not world.ready():
            return JSONResponse(
                status_code=503,
                content={"code": "WORLD_BUILDING", "message": world.waiting_message()},
                headers={"Retry-After": "5"},
            )
    return await call_next(request)


# Registered last, which in Starlette means outermost: the middleware added most
# recently wraps everything before it. That ordering matters here. The 503 above
# is a JSONResponse returned without calling the rest of the stack, so with CORS
# on the inside the browser saw "blocked by CORS policy" instead of the sentence
# explaining that the ledger was still being built — turning a designed waiting
# state into an unexplained failure on every screen.
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


for router in (
    auth.router,
    records.router,
    seals.router,
    witness.router,
    anchor.router,
    models.router,
    governance.router,
    ledger.router,
    workspace.router,
):
    app.include_router(router, prefix="/api")


# --------------------------------------------------------------------------
# the built web app, when there is one
# --------------------------------------------------------------------------
# A deployment is usually one container: the API and the static bundle behind a
# single URL. Serving the bundle from here is what makes that possible without a
# second web server, and it is skipped entirely when the bundle is absent, which
# is the normal case in development where Vite serves it on :5173.
_WEB = _ROOT / "frontend" / "dist"


def _mount_web() -> None:
    if not (_WEB / "index.html").is_file():
        return

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=_WEB / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        """
        Hand every unmatched path to the app's own router.

        Registered last, so `/api/...` and `/docs` are matched by their real
        handlers first and only genuine client-side routes reach this. A file
        that exists is served as itself; anything else gets index.html, because
        `/factory/records/doc-123` is a route in the browser and not a file on
        disk.
        """
        candidate = _WEB / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_WEB / "index.html")


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    from . import corpus
    from .ledger_service import chain_summary

    building = not world.ready()
    channels = [] if building else chain_summary()
    return {
        "status": "building" if building else "ok",
        "world": world.snapshot(),
        "channels": channels,
        "ledger_integrity": bool(channels) and all(c["integrity_ok"] for c in channels),
        # Where the documents came from, so "this is real data" is a checkable
        # claim rather than an assurance. Carries the corpus seed, its manifest
        # digest, and the count of documents the chaincode schema would not take.
        "provenance": {
            **corpus.provenance(),
            **({} if building else workspace.ledger_counts()),
        },
        "note": "All data is invented. No real factory, worker or document.",
    }


# Last, deliberately: the catch-all above must be the final route registered or
# it would shadow the API.
_mount_web()
