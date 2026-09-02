# Future work

What is left, in the order it is worth doing. Written to be actionable rather than
aspirational: every item says what "done" looks like and roughly what it costs.

Free-tier figures were checked in **September 2026** and are the single most volatile thing
in this document — Oracle halved its Always Free ARM allocation in June 2026 without
announcing it, so re-check before committing to any of them.

---

## 1. Where the project actually stands

**Built and tested:** the permissioned ledger with RSA-3072 identities, four chaincodes
(`doccustody`, `anchor`, `fedmodel`, `reputation`), the accumulator with membership,
non-membership, aggregation and delay proofs, period seals and completeness proofs, the
attesting-witness rule with commit–reveal assignment, epoch digests and fork detection, the
Continuity Gate, the federated continual learning plane, the backend API with a capability
table, a frontend that reads every figure it shows from that API, and the trained detector
served from inside the API. 273 tests, 27 of which are attacks.

**Not built:** the items below.

---

## 2. Engineering that remains

### 2.1 Ledger, small and known

**Done since this list was written.** The cumulative drift check now exists: the gate records
each task's best-ever score and refuses a candidate that has fallen more than sigma below it,
so the per-round bound can no longer be exploited by repetition. `test_damage_kept_just_under
_tau_every_round_is_stopped_by_the_cumulative_bound` runs that attacker for four rounds and
watches the fourth get refused. The phantom `flwr` dependency is gone from `pyproject.toml`
and `backend/requirements.txt`; nothing imported it, and the report only ever cited Flower in
a related-work table, so there was no claim to retract.

| Task | Effort | Why it matters |
|---|---|---|
| Orderer signs the block header | ~2 h | Chain integrity currently detects *tampering* but not *fabrication* by whoever controls the store |
| Client signs its own proposal | ~1 h | Only endorsers sign today; the submitter's authorisation is implied, not proved |
| Reputation consumes findings automatically | ~half day | `report_falsification` writes the penalties; a human still has to apply them |

### 2.2 Run it on real Hyperledger Fabric

`model/fabric/` holds the same three chaincodes as genuine Fabric contracts plus a
docker-compose network, and **no peer has ever executed them**. Everything the report claims
about performance comes from the Python chain and is labelled that way.

Needs Docker and ~16 GB. Done when `make fabric-up && make fabric-deploy` commits a record
and the numbers in `results/` are regenerated from Fabric rather than from the simulation.
This is the single largest credibility gain available for the effort.

### 2.3 Frontend and backend — wired

**Done.** The frontend held its entire world as literals in `src/lib/data.ts` and
`src/lib/anchor.ts`: five records, a formulaic block list, two hand-written gate decisions,
and a completeness checker that computed the "root of what you hold" in the browser with an
xorshift. Both files are deleted. Every figure on every screen is now a response from the
API, and the API's world is built from `data/corpus/`.

What that means concretely:

- **688 corpus documents on the ledger**, committed with their own rows and their own
  corpus identifiers, so `doc-cha-w3-014042` on screen is that document in
  `data/corpus/`, byte for byte, and the Merkle root is the root of those exact rows.
  1,050-odd blocks, 28 period seals, 3 accumulator epochs, 4 gate decisions.
- **The demonstrations are the corpus's, not ours.** The completeness checker catches the
  withholding event that `adversary_trace.json` defines — the trace names the disclosed
  set, the seed grants exactly that set, and the shortfall falls out of the arithmetic.
  The witness panel shows `format_only` on the document the trace calls lazily witnessed.
- **The buttons do what they say.** Sealing a record parses a CSV and commits it; the
  auditor's "Run" performs real Merkle disclosures and writes receipts; endorsing a motion
  writes to the server; the absence proof is a Bezout witness from the contract.
- **The mechanisms can now be operated, not only watched.** A factory can close an open
  period and reopen a closed one with a recorded reason — which makes the contract's
  mid-revision state reachable from the product for the first time, and a completeness
  check on a reopened period correctly refuses to serve the settled count. The consortium
  can attach a real delay proof to an epoch that has none: 262,144 sequential squarings,
  a couple of seconds to produce and about two milliseconds to check.
- The **three-check verification panel is still three rows**, with `forgeable_by_trapdoor`
  carried on the wire so the interface cannot forget which one a trapdoor holder could forge.
- The `commit_record` → `amend_seal` dead end is fixed and the seed uses the three-step
  route. Confirmed working.

**Surface audit — every route against every screen.** Cross-checked from the API's own
OpenAPI document against `frontend/src/lib/api.ts` and the components that call it.
**45 of 61 routes are reached by a page. No client method points at a route that does not
exist.** The remaining 16 are deliberate, in three groups:

*Redundant reads (5).* `GET /anchor/anchored/{prime}`, `GET /anchor/epochs/{n}`,
`GET /ledger/blocks/{n}` and `GET /ops/incidents/{id}` are all served by the list endpoint
beside them. `GET /governance/members` is superseded by `GET /orgs`, which returns the same
membership plus channel data — worth deleting rather than maintaining two answers to one
question.

*Things a browser cannot honestly do (6).* `POST /model/gate`, `/model/rounds` and
`/model/benchmarks` need three organisations to each evaluate the candidate locally and
sign the result with their own private key; no browser holds a member's key, and a UI that
pretended to would be inventing the signatures the whole mechanism rests on. The same is
true of `POST /seed-rounds`, `/commit` and `/reveal`: commit–reveal is only unpredictable
because each member's share is that member's secret. Replay and inspection are the correct
interface for both, and both exist.

*Now surfaced.* The gate's cumulative bound is rendered: `CUMULATIVE_REGRESSION` has its own
verdict sentence on the decision page, the per-task table gained **best ever** and **below
best** columns with `null` shown as "no baseline yet" rather than zero, sigma joined the rule
panel, and `GET /api/model/high-water` serves the marks the bound is measured against —
because a ceiling nobody can inspect is a number the operator could be moving.

*Not surfaced yet, and worth doing (4).* `POST /anchor/epochs` — folding a batch needs to
know what is already anchored, and there is no bulk way to ask; a `list_unanchored` on the
contract would fix it in an hour. `POST /seals/{bucket}/amend` — the UI now does step one
of the three-step route (reopen) and step two (commit, via Upload), but nothing joins them
to step three. `GET /seed-rounds/{id}` and `GET /health` have client methods and no panel.
`POST /grants` is superseded by the request-and-answer flow.

**The detector is now actually run.** Everything about the learning plane was governance —
which benchmark was sealed, who signed what, whether the gate promoted it — and none of it
ever scored a document. There was a trained network in `model/artefacts/` that nothing
loaded. `backend/app/detector.py` loads it and `POST /api/records/{id}/screen` runs it,
scoped exactly like reading the record. It is 3,796 parameters and about 18 KB, it runs on
the CPU in roughly a millisecond, and there is no model server and no GPU.

Two things that were worth being careful about. `Detector()` defaults its input width to
`model.datagen.N_FEATURES`, which is **16** — the old extractor — while the trained artefact
is **25** wide from `data/features.py`; constructing it without an explicit `n_features`
raises a shape error on load, and it is the easiest way to get a deployment wrong. And the
measured error rates travel with every score rather than being a second call, because a
probability sitting a few centimetres below a cryptographic proof invites a reader to treat
the two as the same kind of fact. The response says what the score is not, and the screen
prints it.

**Six things the ledger side should know**, found while wrapping it. None is a blocker and
none has been worked around silently.

1. **`publish_beacon` takes its own bar as an argument.** It compares
   `proof.iterations >= args["minimum_iterations"]`, both supplied by the publisher, so
   today the delay requirement is set by the party being constrained. The API is the only
   thing holding it steady (`settings.anchor_minimum_iterations`, 2^18). It belongs in
   channel configuration beside the group parameters. ~1 h, and it changes what the
   report can honestly claim about the beacon.
2. **Blocks are not persisted.** `WorldState` writes to SQLite; `Channel.blocks` is a list
   in memory. Pointing `BREADCRUMBS_LEDGER_PATH` at a file therefore restored the state and
   lost the history — 688 records served over a chain reporting height 1, with the block
   explorer empty while every other screen was full. The API now defaults to `:memory:` and
   rebuilds on boot. Persisting the block log is ~half a day and would remove a 40-second
   cold start.
3. **`witness_requirement` has no historical view.** It answers for the round active *now*,
   so a record committed before the consortium adopted the rule comes back `required: true`
   with no attestations — which reads on screen as an assigned witness having refused to
   sign. The API compensates by comparing the record's commit time with the round's
   `opened_at` and returning `predates_rule`. A `witnessed_under_round` field written onto
   the record at commit time would be better, and is the ledger's to add.
4. **`VALID_TYPES` is missing `production_output`.** The corpus generates five record types
   and the chaincode names four of them plus `compliance_certificate`, which the corpus does
   not produce. 193 of 881 documents in the demo window — 22% — cannot be committed at all.
   The API counts and reports them on `/api/health` rather than dropping them quietly, but
   the schemas should agree.
5. **One factory is on the document channel.** `create_channel(DOCUMENT_CHANNEL, [Apex,
   Primark, BV, BGMEA])` with `AND(ApexTextileMSP, BVCertificationMSP)` endorsement means a
   record owned by Noor or Crescent cannot be committed there. All six corpus sites are
   therefore mapped to Apex, which is honest but flattens a multi-tenant story the
   Chamber's network view otherwise tells. A channel per factory is the real fix.
6. **Nothing measures uptime or latency.** The operations page used to draw a 99.95% line
   from a formula. It now reports verification counts from the receipts on the chain and
   says "not measured" for the rest, which is worth keeping when the deployment work in §5
   happens.

**What the training run produced**, since the registry now shows it rather than a fixture.
Both waves put two candidates to the gate — one rehearsing from the shared memory bank, one
trained the ordinary way — from the same weights, the same NumPy stream and the same Torch
seed, so the only difference between them is the method:

| Wave | Rehearsal, wage change | Ordinary, wage change | Gate |
|---|---|---|---|
| 2 (`forged_certificate`) | −6.5 points | −33.6 points | **both refused** |
| 3 (`chemical_misreporting`) | −1.9 points | −35.9 points | rehearsal **promoted**, ordinary refused |

Rehearsal cuts forgetting by 5× and 19×. It is still refused at wave 2, for being 1.5 points
outside a 5-point tolerance. That case is worth keeping in the demo rather than tuning away:
it is the one that shows the gate constraining the method the authors are advocating.

---

## 3. Data

### 3.1 The synthetic corpus — primary

Built in `data/`, documented in `data/README.md` and `data/data_card.md`, with the
open choices and their justifications in `data/design_decisions.md`. **Done.** It carries
row-level records
and a labelled adversary trace of 8 events across 5 attack types.

Review checklist, all four now checked:

- Same seed twice → byte-identical output. `data/tests/test_determinism.py`.
- A trivial baseline scores **well short of perfect**. `data/tests/test_trivial_baseline.py`.
- `cross_inconsistency` cases are genuinely undetectable from a single document.
  `data/tests/test_cross_inconsistency_undetectability.py`, and independently
  `data/tests/test_features.py::test_cross_inconsistency_is_not_claimed_to_be_visible`,
  which asserts that *no* feature in the extractor separates them by as much as one
  robust standard deviation. Measured detection is 12.9% against a 9.1% false-positive
  rate — indistinguishable, which is the correct answer.
- Every adversary event resolves to documents that exist. `data/tests/test_adversary_consistency.py`.

**The gap that had to be closed before any of it could be trained on.** The corpus is
deliberately messy — four date formats, numbers stored as strings, inconsistent casing,
all scaled by a per-site factor. The feature extractor in `model/datagen` was written
against the older clean generator and raised on **99.5%** of these documents; only 19 of
the first 4,150 survived it. `data/features.py` replaces it: 24 features over all five
record types, every value coerced before it is used, and 19,980 of 19,980 documents
extracting in about 7 seconds with nothing non-finite.

Two things it deliberately does **not** do, both tested. It does not use messiness as a
feature — trailing whitespace and date formats correlate with the site, so a model given
them would learn to name the factory rather than find the fraud. And it does not pretend
to see `cross_inconsistency`.

### 3.2 Real datasets worth downloading

No public dataset of Bangladeshi factory compliance records exists — which is *why* the
synthetic corpus is necessary, and worth saying plainly rather than treating as a gap. What
real data can do is answer the criticism in §7.3 of the report: that our benchmark cannot
separate "the mechanism works" from "this data is easy to summarise". Running the same
federated continual method on real tabular fraud data settles it.

| Dataset | Size | Use |
|---|---|---|
| **IEEE-CIS Fraud Detection** (Kaggle) | ~590k rows, ~1.3 GB | The transfer experiment. Real, messy, imbalanced tabular fraud with hundreds of engineered and raw columns. Partition it across six simulated clients and run prototype replay against sequential FedAvg |
| **Credit Card Fraud** (ULB, Kaggle) | 284k rows, 150 MB | Extreme imbalance (0.17% positive). Tests whether the detector survives a realistic base rate rather than our chosen 4% |
| **PaySim** (Kaggle) | ~6M rows, 470 MB | Synthetic mobile-money transactions with an explicit fraud generator. Useful as a second synthetic corpus written by someone with no stake in our result |
| **Open Supply Hub** (open data, apparel) | small, API | Real factory names, locations and sizes. Use for *metadata realism* in the generator — not for labels |
| **FUNSD / CORD / SROIE** | 200 MB–2 GB | Only if the project moves to document *images*. Forms and receipts with layout annotations |
| **DocTamper** | ~10 GB | Document tampering detection, if the first-mile problem is ever attacked visually |

All comfortably fit the 32 GB RAM budget except DocTamper and any document-image work, which
should be streamed rather than loaded.

**Do not download RVL-CDIP (~37 GB)** unless the project genuinely pivots to document images.
It is a classification corpus and answers no question this system asks.

---

## 4. Training the model

### 4.1 Hardware reality check

The current detector is a 48-unit MLP over 16 features. It trains in **seconds on a CPU**
and needs neither the RTX 5070 Ti nor MLX. Do not build a GPU pipeline for it.

The GPU earns its place only for the row-level model, and even then this is a small job — a
tabular transformer over a few million rows is minutes to an hour, not days. The 5070 Ti's
16 GB is ample; 32 GB system RAM is the tighter constraint if a corpus is loaded whole rather
than streamed.

### 4.2 Environment

The 5070 Ti is Blackwell, compute capability `sm_120`. It needs **PyTorch ≥ 2.7 with CUDA
12.8 wheels** — earlier builds fail with "sm_120 is not compatible with the current PyTorch
installation". The 2.10 line is current.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
python -c "import torch; print(torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))"
# expect: NVIDIA GeForce RTX 5070 Ti (12, 0)
```

On the Mac, `model/ai/` already selects CUDA → MPS → CPU automatically. MLX is not worth
introducing: it would be a second training path to maintain for a model that runs in seconds,
and a divergence between the two would be a source of results nobody can reproduce.

### 4.3 The training sequence

**Stage 0 — reproduce what exists.** `cd model/experiments && python3 fcl_sim.py`. NumPy
only, under a minute. Every number in the report's learning tables comes from here, and it
must still reproduce bit-identically before anything changes.

**Stage 1 — generate the corpus. Done.** `python -m data.cli --seed 7 --scale small --out data/corpus`
(note: `data.cli`, not `corpus.generate`). Verify with `python -m model.run corpus`, which
re-checks the committed benchmark hashes and the feature matrix.

**Stage 2 — the row-level model.** A tabular transformer (FT-Transformer or a small
encoder over row embeddings) replacing `model/ai/net.py`'s MLP. Keep the 16-feature MLP as
the governed production model; train the larger one as evidence that the Continuity Gate is
model-agnostic. Done when the gate promotes and rejects candidates of both kinds.

**Stage 3 — the federated continual run. Done, on CPU, in 25 seconds for all five seeds.**
`python -m model.run train --rounds 15 --seeds 5`. Six sites as clients, Dirichlet α = 0.6,
the three waves as class-incremental stages, prototype replay against sequential FedAvg
with centralised pooling as the ceiling.

| Method | Wave 1 | Wave 2 | Wave 3 | Average | Forgetting |
|---|---|---|---|---|---|
| Sequential FedAvg | 50.0 ± 0.0 | 89.3 ± 5.9 | **67.7 ± 0.9** | 69.0 ± 1.7 | 18.3 ± 2.0 |
| **Prototype replay** | **63.4 ± 2.8** | **97.9 ± 4.0** | 65.4 ± 2.1 | **75.6 ± 1.5** | **11.0 ± 1.2** |
| *Centralised pooling* | *85.5 ± 2.6* | *100.0 ± 0.0* | *63.4 ± 2.5* | *83.0 ± 1.1* | *n/a* |

Balanced accuracy, five seeds, chance is 50.0. Wave 1 under sequential averaging lands at
exactly chance on **every** seed — total forgetting — and replay recovers 13.4 points of it.
This corroborates Figure 3 on row-level documents with a smaller effect (+6.6 average here
against +17.9 in the Gaussian simulation), which is the honest and expected direction.

A bug found in the process, now fixed: `MemoryBank.merge` truncated with `[:k*2]` after
concatenating existing centres first, so once a class held six centres every later
contribution was silently discarded. The bank froze after two merges and rehearsal stopped
covering the stages it existed to protect. It now keeps the centres with the most records
behind them. That single fix moved average accuracy from 70.3 to 75.1.

**Stage 4 — the transfer experiment.** The same method on IEEE-CIS, partitioned six ways.
This is the one that answers §7.3, and its result may go against us. Report it either way.

**Stage 5 — adversarial evaluation. Ledger side done; detector side partly.**
`python -m model.run adversary` maps each of the trace's 5 attack types to the mechanism
that answers it and **runs the 16 tests that actually attempt it** against a live ledger,
reporting what they returned rather than restating a claim. Result: **7 of 8 events
prevented outright, 1 detected and attributed but not prevented** — witness collusion,
where a quorum controlling the seed round can still collude. That row says `recorded`, not
`prevented`, and `test_an_assigned_witness_that_colludes_is_not_stopped_only_recorded`
exists to keep it that way.

Still missing: *how quickly* each attack is caught. There is no latency number yet.

---

## 5. Hosting the prototype

The app is a FastAPI backend over SQLite plus a static React bundle. It is small, it has no
GPU dependency, and it does not need a database server. Three routes, cheapest first.

### Option A — Hugging Face Spaces (free, recommended for judges)

One Docker Space running the FastAPI app and serving the built frontend as static files.
The free CPU tier is **2 vCPU and 16 GB RAM**, which is more memory than Oracle's free ARM
tier now gives, and a Space is a URL anybody can click.

- **Cost:** zero.
- **Good for:** the demonstration. A judge opens a link and the twelve acts are there.
- **Watch for:** free Spaces sleep after inactivity, so the first request after a quiet spell
  is slow; and the filesystem is ephemeral, so the SQLite ledger resets on restart. For a
  demo that reseeds on boot this is fine — arguably better, since every visitor gets a clean
  consortium. Persist to a HF Dataset repo if you need it to survive.
- **The cold start is about 40 seconds**, and it is real work: 688 corpus documents
  committed, a trusted-dealer ceremony, three accumulator epochs, two verifiable-delay
  proofs and four gate decisions. The API no longer waits for it — the seed runs on a
  background thread, the socket opens immediately, and data endpoints return 503 with the
  reason and an estimate until the world exists (the frontend renders that as a loading
  state and retries). This matters here specifically: a Space that sleeps will pay it on
  every wake, and a process manager that waits for the port would otherwise conclude the
  app had failed to start, which is exactly what happened during development.
- **Ship `data/corpus/` with the image, or generate it in the build.** It is gitignored, and
  without it the API starts, says so on `/api/health`, and serves an empty ledger rather
  than inventing one. `python -m data.cli --seed 7 --scale small --out data/corpus` takes
  about five seconds.
- **Effort:** a Dockerfile and a push. Half a day.

### Option B — Oracle Cloud Always Free (free, persistent)

An Ampere A1 ARM VM. **Check the current allocation before planning around it**: Oracle cut
Always Free from 4 OCPU / 24 GB to **2 OCPU / 12 GB on 15 June 2026** with no announcement.
Storage stayed at 200 GB.

- **Cost:** zero, indefinitely.
- **Good for:** a persistent deployment with a real disk, where the ledger survives restarts.
- **Watch for:** A1 capacity is frequently unavailable in popular regions and provisioning can
  take repeated attempts. Everything must be built for ARM64 — fine for Python, occasionally
  annoying for wheels. Oracle has reclaimed idle Always Free instances before.
- **Effort:** one day including TLS and a systemd unit.

### Option C — GCP or Cloud Run on the trial credit

$300 for 90 days. Cloud Run scales to zero, so a low-traffic demo costs cents, and the
always-free e2-micro (1 vCPU, 1 GB) can hold the API afterwards if the frontend is served
elsewhere.

- **Cost:** covered by credit, then a few dollars a month.
- **Good for:** a deployment that has to look professional to a buyer or a sponsor.
- **Watch for:** the credit expires on a clock, not on usage. Do not build a dependency on it.

**Split the frontend out regardless.** Cloudflare Pages or GitHub Pages hosts the React
bundle free and fast, leaving the backend to serve only the API. That halves whatever the
backend has to do and makes the frontend immune to the backend sleeping.

---

## 6. Hosting the AI model — the part that is not actually a problem

Hosting AI models is expensive when the model is large. **This one is not.** The detector is
a 48-unit MLP over 16 features: a few hundred kilobytes of weights, and inference is a matrix
multiply. Even the row-level model in §4.2 is small by 2026 standards.

**So do not rent a GPU.** Run inference on CPU inside the same container as the API. This is
not a compromise; for a model this size a GPU would be slower once you count the transfer.

- **Recommended:** export to ONNX and serve with `onnxruntime` in the FastAPI process. No
  extra service, no extra bill, single-digit milliseconds.
- Training stays local on the 5070 Ti. Only the weights are deployed, and their hash goes on
  the ledger — which the Continuity Gate already records, so the deployed model is
  identifiable from the chain.

If the project ever does need GPU inference:

- **Modal** — serverless GPU defined in Python, scales to zero, monthly free credits. Best fit
  for bursty demo traffic. Cold starts are real.
- **RunPod serverless** — cheapest per-second for sustained work, from around $0.40/h for a
  T4-class card.
- **HF Spaces ZeroGPU** — quota-based H200 access on the free tier. Genuinely useful for a
  demo, unsuitable for anything with a latency guarantee.

For a competition demonstration, **Option A plus CPU inference costs nothing and is the whole
answer.** Spend the credit on the Fabric deployment instead, where it buys credibility that
hosting does not.

---

## 7. Suggested order

1. Corpus generated and checked against §3.1 — unblocks everything else.
2. Stage 2–3 training, so the learning claims are on row-level data.
3. Adversarial evaluation (§4.5) — the missing numbers, and the most valuable ones.
4. Deploy Option A so there is a link to send.
5. Fabric on real Docker (§2.2).
6. Ledger odds and ends (§2.1).
7. Stage 4 transfer experiment, and report it whichever way it goes.
