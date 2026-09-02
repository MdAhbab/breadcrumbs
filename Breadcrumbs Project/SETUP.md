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
make demo     # the twelve-act end-to-end demo — start here
make test     # 273 tests
make api      # API on :8000, docs at /docs
make web      # frontend on :5173
```

Or start the API and the web app together, wait for the ledger to build, and
get the links printed for you:

```bash
python3 ../run.py
```

On Windows without `make`, run the same commands directly:

```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[ml,api,dev]"
.venv\Scripts\python -m model.demo
```

## If Python 3.11 is not your default

`make setup PY=python3.12` — or whichever interpreter you have in range.

## Training the detector

The product runs without a trained model and says so on screen where a score
would go. To train one — about 25 seconds, CPU only, no GPU:

```bash
python -m model.run train
```

That writes `model/artefacts/`, which is what the API loads to score documents.
`python -m model.run --help` lists the rest: evaluation, the adversary scoring,
the benchmarks and the demo.

## Deploying it somewhere

See `DEPLOY.md`. The short version is one container:

```bash
docker build -t breadcrumbs . && docker run -p 8000:8000 breadcrumbs
```

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
├── frontend/    React client
├── data/        the synthetic corpus generator, and the corpus itself
├── docs/        future work, and the figure specifications
├── AUDIT.md     security review, findings, and what is left to do
├── DEPLOY.md    putting it on the internet, including the AI
└── Makefile
```

## Two files that are safe to delete

`backend/ledger.db` and `backend/breadcrumbs.db`. Both are gitignored, and the
API rebuilds the demo world on next boot.

## Troubleshooting

**`ModuleNotFoundError: model`** — the editable install did not run. `make setup`,
or `pip install -e .` from `Breadcrumbs Project`.

**`torch` will not install** — you are on Python 3.13+. Use `make setup PY=python3.12`.

**Port already in use** — `make api` and `make web` use 8000 and 5173. If you
move the API, set `VITE_API_URL` for the frontend and add the frontend's origin
to `BREADCRUMBS_CORS_ORIGINS` for the API. `python3 ../run.py --api-port X
--web-port Y` does both for you.

**The API seems to hang for 40 seconds on startup** — it is not hanging. It is
committing 688 documents, running the accumulator ceremony and training the
detector. It answers `/api/health` from the first moment and reports progress.

**Two files called `run.py`** — the one in the repository root starts the
application; `model/run.py` runs training and benchmarks. Each says so at the
top.
