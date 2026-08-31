# Breadcrumbs API

FastAPI over the ledger in `../model`. It wraps the chain; it never reimplements
a rule that lives in chaincode. Whether a grant covers a field, whether a model
may be promoted, whether an organisation may commit a record — the contract
decides, and this layer carries the question there.

```bash
cd "Breadcrumbs Project"
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000
```

Then http://localhost:8000/docs.

On first boot it seeds the demo world — the same organisations, records, purpose
codes and identifiers the frontend designs were drawn around — and prints
`world state: seeded`. The seed is idempotent; restarting does not double-commit.

## What is where

| Path | Purpose |
|---|---|
| `app/main.py` | App, CORS, lifespan, the chaincode-error handler |
| `app/auth.py` | JWT, the five roles, and the read-only guard for the regulator |
| `app/ledger_service.py` | The bridge to `model/`. The only module that talks to the chain |
| `app/db.py` | Off-chain store: document bodies, salts, proposals, incidents |
| `app/seed.py` | The demo world |
| `app/routers/` | `auth`, `records`, `models`, `governance`, `ledger` |

## The two endpoints worth reading first

`POST /api/verify` proves one row of a record against the committed root and
returns the disclosure, the recomputed root and the ladder. The scope check is
the contract's: asking for a field the grant does not cover returns 403 carrying
the chaincode's own sentence.

`POST /api/model/gate` runs the Continuity Gate over signed evaluations and
returns exactly what the ledger recorded, including the per-task table.

## Storage

Two SQLite files, both gitignored and both safe to delete:

- `ledger.db` — blocks and world state
- `breadcrumbs.db` — the off-chain store

Deleting them and restarting rebuilds the demo world from scratch.
