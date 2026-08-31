# Setting up on a fresh machine

Cloned the repo and want it running? This is the whole list.

## Requirements

| Need | Why | Note |
|---|---|---|
| Python **3.10–3.12** | the ledger, the API, the learning plane | **not 3.13+** — no PyTorch wheels yet |
| Node **18+** | the frontend | only if you want the web UI |
| Docker + ~16 GB | real Hyperledger Fabric | optional; everything else runs without it |

## One command

```bash
cd "Breadcrumbs Project"
make setup
```

That creates `.venv`, installs the package with all extras, and installs the
frontend's node modules. Then:

```bash
make demo     # the eight-act end-to-end demo — start here
make test     # 91 tests
make api      # API on :8000, docs at /docs
make web      # frontend on :5173
```

On Windows without `make`, run the same commands directly:

```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[ml,api,dev]"
.venv\Scripts\python -m model.demo
```

## If Python 3.11 is not your default

`make setup PY=python3.12` — or whichever interpreter you have in range.

## Real Hyperledger Fabric

Needs Docker running. On WSL2 make sure Docker Desktop has WSL integration
enabled for your distro.

```bash
make fabric-up       # fetches fabric-samples, starts the network, creates channels
make fabric-deploy   # installs and commits both chaincodes
make fabric-down
```

Read `model/fabric/README.md` first — those assets are written but have never
been executed, and the README is explicit about what that means.

## Where things live

```
Breadcrumbs Project/
├── model/       the system: ledger, chaincode, Merkle, learning plane
├── backend/     FastAPI over it
├── frontend/    React client and the design specification
├── deck/        the presentation prompt
├── AUDIT.md     security review, findings, and what is left to do
└── Makefile
```

## Two files that are safe to delete

`backend/ledger.db` and `backend/breadcrumbs.db`. Both are gitignored, and the
API rebuilds the demo world on next boot.

## Troubleshooting

**`ModuleNotFoundError: model`** — the editable install did not run. `make setup`,
or `pip install -e .` from `Breadcrumbs Project`.

**`torch` will not install** — you are on Python 3.13+. Use `make setup PY=python3.12`.

**Port already in use** — `make api` and `make web` use 8000 and 5173. The
frontend proxies `/api` to 8000, so if you move the API, update
`frontend/vite.config.ts`.
