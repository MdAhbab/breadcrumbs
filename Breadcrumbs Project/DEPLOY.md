# Deploying Breadcrumbs

Everything you need to put this on the internet. Written for the person who has
never deployed it before.

`SETUP.md` is for running it on your own machine. This is for running it
somewhere other people can reach.

---

## 1. The short version

There are **two processes**, not four:

| Process | What it is | Port |
|---|---|---|
| The API | FastAPI. **The blockchain and the AI both live inside it.** | 8000 |
| The web app | A static bundle. Holds no data of its own. | 5173 in dev |

In a deployment the second one usually stops being a process at all: you build
it once into static files and the API serves them. That is what the `Dockerfile`
in this folder does, and it is why the whole thing is one container.

```bash
docker build -t breadcrumbs .
docker run -p 8000:8000 -e BREADCRUMBS_SECRET_KEY="$(openssl rand -hex 32)" breadcrumbs
```

Open `http://localhost:8000`. That is the entire deployment.

---

## 2. Deploying the AI

This is the part that confuses people, so it gets its own section.

### There is nothing separate to deploy

Most AI projects need a model server, a GPU, a queue, and a second bill. **This
one does not**, and that is a fact about the model rather than a corner cut.

Here is the whole detector:

| | |
|---|---|
| Parameters | **3,796** |
| Size on disk | **18 KB** — `model/artefacts/detector-replay.pt` |
| Input | 25 numbers extracted from one document |
| Shape | Two hidden layers of 48 units, tanh, four-way output |
| Time to score one document | About **1 millisecond**, on a CPU |
| GPU needed | **No.** On a model this small a GPU is slower once you count moving the data to it |

It is loaded once, on first use, by `backend/app/detector.py`, and it stays in
memory in the API process. Deploying the AI means **copying an 18 KB file into
the container**, which the `Dockerfile` already does.

### The three files that matter

All in `model/artefacts/`:

| File | What it is | Without it |
|---|---|---|
| `detector-replay.pt` | The trained weights | No scoring |
| `scale-replay.npz` | The mean and standard deviation each feature is normalised by | Scores would be nonsense |
| `operating-point-replay.json` | The threshold, and which false-positive budget it was chosen for | No way to turn a score into a decision |

`training.json` is a fourth file. It is not needed to run, but the interface
reads it to show the measured error rates beside every score, and Figure 4 in
the paper comes from it. Ship it.

### If the artefacts are missing

Nothing breaks. The API starts, the product works, and every screen that would
show a score says **"No detector is deployed"** with the command to fix it.
That is deliberate: an AI that silently invents scores when its weights are
missing is worse than one that admits it is not there.

To train one:

```bash
cd "Breadcrumbs Project"
python -m model.run train      # about 25 seconds, five seeds, CPU only
```

That writes all four files. There is no GPU step. If you want to see what it
produced:

```bash
python -m model.run eval
```

### How to check the AI is really working after you deploy

```bash
curl https://YOUR-URL/api/model/detector
```

You should get `"trained": true` and a block of measured rates. If you get
`"trained": false`, the artefacts did not make it into the image.

Then sign in as the factory, open any record, scroll to **"What the detector
thinks"** and press *Score this record*. A number, a threshold and the error
rates should appear.

### What the AI is not

The score is **not evidence** and the product is careful to say so on screen.
The ledger proves a record has not been changed since it was committed. The
detector only guesses whether the record looks wrong, and at the shipped
operating point it is wrong about **one clean document in ten**.

Measured over five seeds:

| | |
|---|---|
| Catches | 77.3% of anomalies |
| Flags clean documents | 10.4% |
| Balanced accuracy | 83.5% |
| ROC-AUC | 89.4% |
| On `cross_inconsistency` | **8.3%** — chance |

That last row is the honest one. A cross-inconsistency is two documents that are
each perfectly valid and disagree with one another. Nothing in a single document
reveals it, so the detector is at chance there **by construction**. Catching it
needs the ledger, not the model. Do not let anyone present that number as a bug
to be fixed with more training.

### Changing the operating point

The threshold is a policy choice, not a model property. `HEADLINE_BUDGET` in
`model/run.py` picks it. The measured trade-off:

| Budget | Catches | Flags clean | Balanced |
|---|---|---|---|
| 1% | 67.3% | 1.0% | 83.1% |
| 5% | 74.4% | 5.1% | **84.7%** |
| 10% (shipped) | 77.3% | 10.4% | 83.5% |

**5% beats 10% on balanced accuracy while flagging half as many clean
documents.** It wins on every seed. If an auditor is going to look at everything
flagged, 5% is probably the better setting. Change the constant and re-run
`python -m model.run train`.

---

## 3. Option A — Hugging Face Spaces (free, best for judges)

Free, gives you a URL anybody can click, and 2 vCPU with 16 GB RAM is more than
enough.

1. Create a new **Docker** Space.
2. Push this repository to it. The `Dockerfile` in `Breadcrumbs Project/` is the
   one it needs, so either put the Space at that folder or move the Dockerfile
   to the repository root and adjust the `COPY` paths.
3. In the Space settings, add a secret:

   | Name | Value |
   |---|---|
   | `BREADCRUMBS_SECRET_KEY` | any long random string |

4. Set the Space's app port to **8000**.

**Two things to expect.**

The **first request after a quiet spell is slow.** Free Spaces sleep, and waking
one costs the cold start described below. This is not a fault.

The **ledger resets on restart.** The filesystem is ephemeral and the chain is
rebuilt in memory anyway. For a demo this is arguably better: every visitor gets
a clean consortium.

---

## 4. Option B — a virtual machine

Any small Linux box. 2 CPU and 2 GB RAM is comfortable; PyTorch CPU is the
largest thing in the image.

```bash
git clone <your repo>
cd "Breadcrumbs Project"
docker build -t breadcrumbs .
docker run -d --restart unless-stopped -p 80:8000 \
  -e BREADCRUMBS_SECRET_KEY="$(openssl rand -hex 32)" \
  --name breadcrumbs breadcrumbs
```

Put a reverse proxy in front for TLS. Nothing in the app needs to know about it.

Without Docker, run the API under `systemd` and point nginx at it. Build the
frontend first (`npm run build --prefix frontend`) so the API can serve it.

---

## 5. Option C — split the frontend off

Useful if you want the web app to stay fast while the API sleeps.

1. `npm run build --prefix frontend` with `VITE_API_URL=https://your-api-host`
2. Upload `frontend/dist/` to Cloudflare Pages, GitHub Pages or Netlify.
3. Deploy the API on its own, and **add the web app's origin to
   `BREADCRUMBS_CORS_ORIGINS`** or every request from the browser will be
   blocked.

---

## 6. Environment variables

All are read with the prefix `BREADCRUMBS_`.

| Variable | Default | Set it when |
|---|---|---|
| `BREADCRUMBS_SECRET_KEY` | a development placeholder | **Always in production.** The app refuses to start with the default when debug is off |
| `BREADCRUMBS_DEBUG` | `true` | Set `false` in production |
| `BREADCRUMBS_CORS_ORIGINS` | localhost 5173 and 3000 | The web app is on a different host. JSON array: `["https://example.org"]` |
| `BREADCRUMBS_DATABASE_URL` | a file beside the backend | You want the off-chain store somewhere else |
| `BREADCRUMBS_LEDGER_PATH` | `:memory:` | Leave it alone — see below |
| `BREADCRUMBS_ANCHOR_MODULUS_BITS` | `1024` | You want the report's 3072. Costs about a minute of prime search at every boot |
| `BREADCRUMBS_ANCHOR_MINIMUM_ITERATIONS` | `262144` | You want a longer delay proof |
| `PORT` | `8000` | Your host assigns a port |

### Why the ledger is in memory

`model/ledger/network.py` saves world state to SQLite but keeps the block list
in memory. Pointing `BREADCRUMBS_LEDGER_PATH` at a file therefore restores the
**state** and loses the **history**: you get 688 records over a chain reporting
height 1, and the block explorer — the first screen a sceptic opens — is empty
while every other screen is full.

For a system whose entire claim is that the history is the evidence, keeping the
state and discarding the history is the wrong half to save. So it rebuilds both
on every boot. Do not change this until the block log is persisted too.

---

## 7. The cold start

**About 40 seconds**, once per boot. It is real work:

- 688 corpus documents committed, each hashed into a Merkle tree
- a trusted-dealer ceremony for the accumulator parameters
- three accumulator epochs folded
- two verifiable-delay proofs, 262,144 sequential squarings each
- the detector trained through four Continuity Gate decisions

**The API does not block while this happens.** The socket opens immediately, the
seed runs on a background thread, and data endpoints return `503` with a sentence
saying what is happening and roughly how long is left. The web app renders that
as a loading state and retries by itself.

This matters for your health check. **Treat "building" as alive.** A checker that
waits for the port and gives up after 30 seconds will conclude the app failed to
start — which is exactly what happened during development.

```bash
curl https://YOUR-URL/api/health
# {"status":"building","world":{"state":"building","elapsed_seconds":12.4, ...}}
```

Wait for `"state": "ready"`.

---

## 8. Check it worked

In order. Each one takes a few seconds.

```bash
# 1. The API is alive and the world is built
curl -s https://YOUR-URL/api/health | grep '"state"'

# 2. The corpus made it into the image
curl -s https://YOUR-URL/api/health | grep records_on_ledger    # expect 688

# 3. The chain verifies
curl -s https://YOUR-URL/api/health | grep ledger_integrity     # expect true

# 4. The AI is deployed
curl -s https://YOUR-URL/api/model/detector | grep '"trained"'  # expect true
```

Then in a browser:

1. Open the URL. The landing page should say **688 documents… seed 7**.
2. Sign in as the **buyer** → *Completeness*. It should say **40 sealed / 39
   disclosed** with two different hashes.
3. Sign in as the **factory** → open any record → *Score this record*. A score
   and its error rates should appear.
4. Open **Ledger**. It should say *Chain verified* over a thousand blocks.

If all four work, the deployment is complete.

---

## 9. Troubleshooting

**Everything returns 503 and never stops.** The world build failed. Check
`/api/health` — `world.error` carries the exception. Usually a missing corpus.

**`records_on_ledger` is 0.** `data/corpus/` did not make it into the image.
It is in the repository, so check your `.dockerignore` and your build context.

**`"trained": false` on `/api/model/detector`.** `model/artefacts/` did not make
it in. Run `python -m model.run train` and rebuild.

**The page loads but every panel says the API is unreachable.** CORS. The web
app's origin is not in `BREADCRUMBS_CORS_ORIGINS`. This does not apply in a
single container, where both are the same origin.

**The app refuses to start, complaining about the secret key.** Correct
behaviour. Set `BREADCRUMBS_SECRET_KEY`.

**A blank page, and the network tab shows `index.html` where JSON was expected.**
The static catch-all is shadowing the API. It must be registered after every
router; there is a test for this (`test_serving_the_web_bundle_does_not_shadow_the_api`).

**PyTorch will not install.** You are on Python 3.13+. The image pins 3.11.

---

## 10. What this deployment is not

Worth saying plainly, because a judge will ask.

- The chain is **our own Python implementation**, not a real Hyperledger Fabric
  network. `model/fabric/` holds genuine Fabric chaincode that no peer has ever
  executed. Every performance figure comes from the Python chain and is labelled
  that way.
- The accumulator ceremony uses a **1024-bit modulus by default** so boot is
  quick. The report specifies 3072 and the interface always shows the real bit
  length, so a development deployment says 1024 on screen rather than claiming
  the production figure.
- **Nothing measures uptime or latency.** The operations page counts real
  verifications from the chain and reports the rest as "not measured".
- All data is synthetic. No real factory, worker or document.
