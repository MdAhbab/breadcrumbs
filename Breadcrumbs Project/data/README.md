# Breadcrumbs Synthetic Corpus Generator

A deterministic streaming generator for synthetic RMG compliance documents, continual learning violation waves, and permissioned ledger adversary traces.

Designed for the **Breadcrumbs** academic prototype and Blockchain Olympiad Bangladesh submission.

---

## 1. Quick Start

### Basic CLI Usage
Generate a small (~20,000 documents) synthetic corpus in under 15 seconds:
```bash
python -m data.cli --seed 7 --scale small --out corpus/
```

Generate with custom document count and output directory:
```bash
python -m data.cli --seed 42 --docs 5000 --out custom_corpus/
```

Generate with optional Apache Parquet output:
```bash
python -m data.cli --seed 7 --scale small --parquet --out corpus/
```

Verify bitwise determinism across runs:
```bash
python -m data.cli --verify-determinism
```

---

## 1a. Where the rest of the documentation is

| File | What it holds |
|---|---|
| `data_card.md` | The scientific data card: disclaimers, intended uses, and the ways a synthetic corpus can flatter the models measured on it. Copied into every generated corpus. |
| `design_decisions.md` | Every place the specification left a choice open, what was chosen, and why. Wage grade scales, anomaly severity, the messiness model. |
| `../docs/future_works.md` §3 | What the corpus still does not carry, and the real datasets worth adding. |

---

## 2. Benchmark Timings Across Scales

Evaluated on a modern multi-core laptop (Apple Silicon / Python 3.11):

| Scale | Approximate Docs | Generation Time | Peak RAM | Typical Use Case |
|---|---|---|---|---|
| `small` | ~20,000 | ~4.5 s | < 45 MB | Unit tests, local CI, fast iteration |
| `medium` | ~200,000 | ~42.0 s | < 60 MB | Full federated training, benchmark evaluation |
| `large` | ~1,000,000 | ~3.5 min | < 75 MB | Large-scale stress testing, scale experiments |

*Note: Streaming generation writes shards incrementally to disk with fixed-size working buffers, maintaining low memory consumption at all scales.*

---

## 3. Output Directory Structure

The generator produces a self-describing corpus tree:

```
corpus/
├── manifest.json              # PRNG seed, config, Dirichlet per-site matrices, all file SHA-256 hashes
├── data_card.md               # Scientific data card with explicit disclaimers & flattery warnings
├── ground_truth.json          # Per-document labels, anomaly kind, target row index, continuous severity
├── adversary_trace.json       # Chronological timeline of the 8 ledger attack types and ground truth
├── stats.json                 # Aggregate counts, anomaly rates, per-site and per-wave breakdowns
├── documents/                 # Sharded corpus partitioned by site and wave
│   ├── site=gazipur/
│   │   ├── wave=1/part-2025-01-gazipur.jsonl.gz
│   │   └── ...
│   └── site=ashulia/ ...
└── benchmarks/                # Held-out evaluation benchmarks (disjoint from training shards)
    ├── wave1.jsonl.gz         # Wave 1 end-distribution test set
    ├── wave2.jsonl.gz         # Wave 2 end-distribution test set
    ├── wave3.jsonl.gz         # Wave 3 end-distribution test set
    ├── cross_wave.jsonl.gz    # Comprehensive cross-wave test set (measuring catastrophic forgetting)
    └── hashes.json            # SHA-256 digests for all benchmark files
```

---

## 4. Python Adapter API

For downstream ML and ledger code, the package exposes a backward-compatible adapter interface:

```python
from data import DocumentGenerator, CorpusConfig

# Initialize generator
gen = DocumentGenerator(seed=7, anomaly_rate=0.04)

# Generate in-memory documents
docs = gen.generate(n_docs=500)

# Generate balanced sample of a specific anomaly kind for training
chem_docs = gen.generate_of_kind(kind="arithmetic", n=200)
```

---

## 5. Running the Acceptance Test Suite

Run the full acceptance test suite covering all 10 specifications:
```bash
pytest data/tests -v
```
