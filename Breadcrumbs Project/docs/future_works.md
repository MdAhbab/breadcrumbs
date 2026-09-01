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
table, and a fixture-driven frontend. 210 tests, 26 of which are attacks.

**Not built:** the items below.

---

## 2. Engineering that remains

### 2.1 Ledger — small, known, and in the report's limitations

| Task | Effort | Why it matters |
|---|---|---|
| Orderer signs the block header | ~2 h | Chain integrity currently detects *tampering* but not *fabrication* by whoever controls the store |
| Client signs its own proposal | ~1 h | Only endorsers sign today; the submitter's authorisation is implied, not proved |
| Cumulative drift check for the Continuity Gate | ~1 day | The gate bounds regression per round, not across rounds. This is the attack in our suite that succeeds |
| Reputation consumes findings automatically | ~half day | `report_falsification` writes the penalties; a human still has to apply them |
| A real Flower `Strategy` wrapping the aggregation | ~half day | `flwr` is a declared dependency that nothing imports. Either write it or amend the report — do not leave it |

### 2.2 Run it on real Hyperledger Fabric

`model/fabric/` holds the same three chaincodes as genuine Fabric contracts plus a
docker-compose network, and **no peer has ever executed them**. Everything the report claims
about performance comes from the Python chain and is labelled that way.

Needs Docker and ~16 GB. Done when `make fabric-up && make fabric-deploy` commits a record
and the numbers in `results/` are regenerated from Fabric rather than from the simulation.
This is the single largest credibility gain available for the effort.

### 2.3 Frontend and backend

Owned by the other agent. Two things worth flagging from this side:

- The **three-check verification panel must stay three rows.** A combined badge throws away
  the defence that makes the trusted-dealer modulus survivable.
- The dead end they found in `commit_record` → `amend_seal` **is fixed**. The route is now
  three steps: `reopen_seal` (with a reason, recorded before the change), `commit_record`,
  `amend_seal`. Their seed and tests were updated; a genuinely late record now has a path in,
  and a reopened period reports itself as mid-revision rather than serving a stale count.

---

## 3. Data

### 3.1 The synthetic corpus — primary

Generated from `docs/synthetic_corpus_prompt.md`. Two things it must carry that the current
corpus does not: **row-level records** (so a detector learns from records rather than from
sixteen hand-designed statistics), and a **labelled adversary trace** — withheld records,
retroactive edits, back-dated seals, forked histories, witness collusion. Without the trace
the ledger's guarantees can be asserted but not scored, which is most of what this project
claims.

Review checklist when the generator comes back:

- Same seed twice → byte-identical output.
- A trivial baseline (logistic regression on a few obvious features) scores **well short of
  perfect** on the realistic mix. If it scores 99%, the corpus is too easy and every result
  computed on it is meaningless. This is the first thing a judge will try.
- `cross_inconsistency` cases are genuinely undetectable from a single document.
- Every adversary event resolves to documents that exist.

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

**Stage 1 — generate the corpus.** `python -m corpus.generate --seed 7 --scale medium`.
Check it against §3.1 before training anything on it.

**Stage 2 — the row-level model.** A tabular transformer (FT-Transformer or a small
encoder over row embeddings) replacing `model/ai/net.py`'s MLP. Keep the 16-feature MLP as
the governed production model; train the larger one as evidence that the Continuity Gate is
model-agnostic. Done when the gate promotes and rejects candidates of both kinds.

**Stage 3 — the federated continual run.** Six clients, Dirichlet α = 0.6, three waves,
prototype replay against sequential FedAvg and centralised pooling. This is
`model/ai/federated.py` with a different network. On the 5070 Ti expect tens of minutes for
all five seeds.

**Stage 4 — the transfer experiment.** The same method on IEEE-CIS, partitioned six ways.
This is the one that answers §7.3, and its result may go against us. Report it either way.

**Stage 5 — adversarial evaluation.** Score the detector against the corpus's adversary
trace, and score the *ledger* against it too: what fraction of withheld records, back-dated
seals and forked histories does the system catch, and how quickly? No number of this kind
exists yet, and it is the most valuable one the project could produce.

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
