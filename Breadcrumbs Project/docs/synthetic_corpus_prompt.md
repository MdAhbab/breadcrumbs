You are writing a **synthetic data generator** for an academic prototype called
Breadcrumbs: a permissioned blockchain that makes a garment factory's own internal
compliance records provable, plus a federated continual-learning detector that the ledger
governs. It is a student competition submission for the Blockchain Olympiad Bangladesh.

Nothing you generate is real and nothing may be presented as real. No actual factory,
worker, buyer, auditor or document is being represented. You are building an instrument
that lets us **measure a system honestly**, not a claim about the garment industry.

Deliver a Python package. Do not deliver data.

### The two things this corpus must support

Most synthetic dataset generators only feed a model. This one has to feed two evaluations
at once, and the second is the unusual half:

1. **The detector axis.** Documents with realistic, labelled anomalies, partitioned
   non-identically across factories, arriving in waves over time so that a continually
   learning model can be shown to forget and then shown not to.
2. **The ledger axis.** A separate, labelled **adversary trace**: a timeline of attempts to
   tamper with, withhold, back-date, duplicate or fork the record history. Without this, a
   blockchain's guarantees cannot be scored at all — you can only assert them. This is the
   part most such generators omit, and it is the part we care about most.

Read §7 before you write anything else, because the adversary trace constrains the
document schema.

---

## 1. Domain, in enough detail to be plausible

Bangladesh's ready-made garment sector. A factory of 800-4,000 workers produces, every
month, a set of internal documents that it must later justify to an outside party — a
buyer's compliance team, a social auditor, or a regulator.

Six invented factory sites, which should differ from each other in persistent, learnable
ways (size, wage level, record-keeping discipline, seasonality, which record types they
produce most):

| Site key | Workers | Character |
|---|---|---|
| `gazipur` | ~2,000 | Large knitwear, disciplined records, high overtime in peak season |
| `ashulia` | ~3,400 | Largest, multi-buyer, most record types, occasional sloppiness |
| `narayanganj` | ~900 | Small, older machinery, heavy maintenance logs |
| `savar` | ~1,600 | Mid-size, strong safety culture after past incidents |
| `chattogram` | ~2,800 | Port-adjacent, chemical-heavy dyeing operations |
| `mirpur` | ~700 | Smallest, thinnest records, most missing fields |

Anchor numbers (use these; do not invent competing ones):

- RMG minimum monthly wage: **12,500 BDT**. Site means should sit between 1.0x and 1.15x
  of this, and stay stable per site over time so "far from what this site normally
  reports" is a meaningful signal.
- Statutory overtime ceiling: **12 hours per week**, so **48 hours** over a four-week
  period.
- Overtime is paid at **twice** the ordinary hourly rate; ordinary hourly rate is
  `basic / 208`.
- Peak export season runs roughly **August to November**; overtime and production volumes
  should rise then, at every site, by a site-specific amount.
- Time span of the corpus: **January 2025 to December 2027**, monthly periods.

---

## 2. Record types and their row schemas

Five record types. Every document is a header plus a list of **rows**. Rows carry raw
fields — **do not pre-compute features**; a downstream model is going to learn directly
from rows, and that is the whole point of this version of the corpus.

Include realistic messiness in every type: missing optional fields, inconsistent casing,
trailing whitespace, occasional transliterated Bangla in free-text fields, dates in two or
three different string formats, numbers occasionally stored as strings. Messiness must be
**site-correlated and persistent** — `mirpur` is sloppier than `gazipur`, every month —
because a detector that can only work on immaculate input proves nothing.

### 2.1 `payroll_register`
One row per worker per period. 200-1,200 rows.
```
worker_ref          "W-04182"   a stable pseudonymous reference, NEVER a name
grade               1..7
days_worked         0..26
basic_bdt           float
ot_hours            float
ot_rate_bdt         float       normally basic/208*2
ot_pay_bdt          float
attendance_bonus_bdt float      often 0
deductions_bdt      float       advances, PF, absence
net_pay_bdt         float       normally basic + ot_pay + bonus - deductions
payment_mode        "bank" | "mfs" | "cash"
paid_on             date string
```

### 2.2 `safety_inspection`
One row per checkpoint. 20-120 rows.
```
checkpoint_ref      "CP-014"
category            "fire" | "electrical" | "structural" | "chemical" | "egress"
certificate_id      "ISO45001-NNNNNCC" where CC = NNNNN mod 97 (a mod-97 check digit)
inspected_on        date string
signed_on           date string   normally 0-10 days AFTER inspected_on
inspector_ref       "INS-07"
result              "pass" | "remediate" | "fail"
remediation_due     date string or null
notes               free text, often empty
```

### 2.3 `chemical_inventory`
One row per substance per period. 15-90 rows.
```
substance_ref       "CHM-0231"
cas_number          plausible CAS format with a valid check digit
opening_kg          float
received_kg         float
consumed_kg         float
disposed_kg         float
closing_kg          float       normally opening + received - consumed - disposed
zdhc_listed         bool
msds_on_file        bool
storage_zone        "A".."F"
```

### 2.4 `machine_maintenance`
One row per servicing event. 30-200 rows.
```
machine_ref         "MC-0417"
machine_type        "overlock" | "flatlock" | "cutter" | "boiler" | "generator"
serviced_on         date string
hours_since_last    int
technician_ref      "TCH-12"
parts_replaced      list of short strings
next_due_on         date string
downtime_minutes    int
```

### 2.5 `production_output`
One row per line per day. 60-600 rows. **This type exists for cross-checking** — see §7.6.
```
line_ref            "L-03"
output_date         date string
units_produced      int
workers_present     int
machine_hours       float
electricity_kwh     float
buyer_code          "BYR-04"    which buyer's order this line ran
```

---

## 3. The anomaly taxonomy — the detector axis

Every document carries ground truth. Anomalies are **injected into rows**, and the row
index is recorded, so both document-level and row-level detection can be scored.

| Kind | Where | What it looks like |
|---|---|---|
| `arithmetic` | payroll, chemical | a stated total does not equal its components. Vary the magnitude: some obvious, many within 1-3% so the task is not trivial |
| `checksum` | safety | a certificate or CAS identifier fails its check digit |
| `overtime` | payroll | hours exceed the statutory ceiling, sometimes just barely |
| `backdating` | safety, maintenance | signed before the event it certifies |
| `outlier` | payroll, chemical, production | a value far from this site's own established normal |
| `duplication` | payroll, maintenance | the same worker or machine appears twice with different values |
| `roundness` | payroll, chemical | implausibly round numbers clustered together, a classic fabrication tell |
| `benford` | payroll, production | the first-digit distribution deviates from Benford's law across the document |
| `cross_inconsistency` | payroll vs production | wages paid imply far more or fewer labour hours than production output and electricity can support. **Only detectable across two documents** |

Requirements:

- Base anomaly rate **4%** across the realistic corpus, configurable. Provide a separate
  **balanced sampling mode** for training a detector, and keep the two clearly separated —
  train balanced, report on the realistic mix.
- Anomaly **severity** must be a graded continuous parameter, not binary. A detector that
  only catches blatant cases should score differently from one that catches subtle ones,
  and the report needs a difficulty axis it did not choose after seeing the results.
- `cross_inconsistency` is the interesting one and must be genuinely undetectable from a
  single document. It is what justifies a shared ledger over a single-document checker.

---

## 4. Time: three waves, plus drift

The detector must learn continually, so anomaly kinds arrive in **waves** and earlier
waves' data becomes unavailable:

- **Wave 1** (2025-01 → 2025-12): `arithmetic`, `overtime` — wage-register inconsistency
- **Wave 2** (2026-01 → 2026-12): `checksum`, `backdating` — forged certificates
- **Wave 3** (2027-01 → 2027-12): chemical `arithmetic`, `outlier` — chemical misreporting

Additionally:

- **Within-wave drift.** The way a given anomaly is expressed should shift gradually across
  a wave, so that a model tested at the end of a wave faces a slightly different
  distribution than it trained on at the start.
- **Seasonality**, as in §1.
- **A recurrence.** Late in wave 3, reintroduce a small number of wave-1 anomalies. This is
  what makes forgetting *measurable in production terms* rather than only on a held-out
  benchmark, and no existing version of this corpus has it.

---

## 5. Federated partition

Data is partitioned across the six sites, and must be **non-IID** — six interchangeable
shards would make the federated result meaningless.

- Use a **Dirichlet partition with α = 0.6** over anomaly kinds per site (match this value;
  it is what the existing code uses).
- Sites also differ in **volume** (proportional to worker count), **record-type mix**, and
  **base rates** — `chattogram` should have more chemical records and more chemical
  anomalies; `mirpur` fewer records and more missing fields.
- Partition must be a **pure function of the seed**, and the per-site assignment must be
  emitted to the manifest so an experiment can be re-partitioned identically.

---

## 6. Benchmarks

For each wave, emit a **held-out benchmark set** that is:

- disjoint from every training shard,
- drawn from the same distribution as the wave's *end*, not its start,
- stored separately with its own file and its own SHA-256, because the ledger commits that
  hash before a training round begins and reveals the contents afterwards.

Also emit one **cross-wave benchmark** containing all waves, for measuring forgetting.

---

## 7. The adversary trace — the ledger axis

**This is the part that makes the corpus unusual, and the part to get right.**

The system under test is a blockchain whose claimed properties are: records cannot be
edited after commitment, corrections are new records that keep the original visible, a
sealed reporting period's record set is complete and provably so, and each record carries
an independent counter-signature. Those claims can only be *scored* if the corpus contains
attempts to violate them, with ground truth about which attempts happened.

Emit `adversary_trace.json`: an ordered list of events, each with a timestamp, an actor, an
attack type, the target record or period, the parameters used, and a ground-truth label.
The document corpus and the trace must be **mutually consistent** — where the trace says a
factory kept a second version of a payroll register, both versions must exist in the
output, flagged.

### The attacks to include

**7.1 `retroactive_edit`** — a document is committed, then a *different* version of the
same logical document appears later carrying the same identity and period. Emit both
versions and the edit delta. Include benign cases too: a genuine correction, properly
declared. A system that flags every change is as useless as one that flags none, and the
benign/malicious ratio should be a tunable parameter.

**7.2 `withholding`** — a factory produces N documents for a period but discloses only
M < N, holding back the ones with anomalies. Emit the full set, the disclosed subset, and
the withheld subset. **This is the single most important attack in the trace**, because
proving that nothing is missing is the system's headline claim and nothing else in the
corpus tests it.

**7.3 `backdated_seal`** — a period is closed late and presented as though it were closed
on time. Record the real and the claimed closing time.

**7.4 `witness_collusion`** — a record's assigned counter-signatory attests to a document
it did not check, and the document is false. Include a graded series: an honest witness, a
lazy witness that signs everything without looking, and a colluding witness that
specifically covers falsified records. The system is *not* expected to stop the third case,
and the corpus must let us quantify how much it does not.

**7.5 `equivocation`** — two members are served different histories for the same period.
Emit both views and the divergence point.

**7.6 `cross_document_fraud`** — a payroll register is falsified in a way that is internally
consistent but contradicts the production and electricity records for the same period. This
is the attack that motivates a *shared* ledger rather than per-factory notarisation, and it
needs `production_output` to exist, which is why it is in §2.5.

**7.7 `duplicate_submission`** — the same document committed twice, or committed to two
different buyer channels with different contents.

**7.8 `late_amendment_abuse`** — a factory that amends sealed periods far more often than
its peers, hiding real changes inside a high volume of trivial ones. Emit the amendment
rate per site so a detector can be scored on separating signal from noise.

Every attack needs a **difficulty parameter**, and a configuration in which the attacker is
*careful* — edits that preserve totals, withholding that preserves counts, amendments that
look routine. An adversary that always leaves obvious traces flatters the system being
tested, and a competition judge will assume that is what happened unless the code shows
otherwise.

---

## 8. What to output

```
corpus/
  manifest.json              seed, version, config, per-site assignment, all file hashes
  data_card.md               §10
  documents/
    site=<site>/wave=<n>/part-*.jsonl.gz     the corpus, sharded
  benchmarks/
    wave1.jsonl.gz  wave2.jsonl.gz  wave3.jsonl.gz  cross_wave.jsonl.gz
    hashes.json                              SHA-256 of each, canonically serialised
  ground_truth.json          per-document labels, anomaly kind, row index, severity
  adversary_trace.json       §7
  stats.json                 counts, rates, per-site and per-wave breakdowns
```

Also offer Parquet as an alternative output format behind a flag, since the row-level model
will read this repeatedly.

---

## 9. Code requirements

- **Python 3.11+**, standard library plus `numpy` only for the core generator. `pandas` and
  `pyarrow` may be imported lazily, and only for the optional Parquet writer.
- **Determinism is a hard contract.** The same seed produces byte-identical output on any
  machine and any OS. That means: a single seeded `numpy.random.Generator` threaded
  explicitly through every function, no reliance on `dict` or `set` iteration order for
  anything that reaches the output, no wall-clock time, no `hash()`, no unordered
  parallelism, and canonical JSON on write (`sort_keys=True`, `separators=(",", ":")`).
  Provide a `verify_determinism()` that generates a small corpus twice and compares hashes.
- **Streaming.** Must generate millions of rows without holding them in memory. Write
  shard by shard.
- **Configurable and introspectable.** A single dataclass holding every knob — scale,
  anomaly rate, severity, Dirichlet α, attack rates, attack difficulty, messiness — with
  documented defaults. Print the effective configuration at startup.
- **A CLI**: `python -m corpus.generate --seed 7 --scale small|medium|large --out corpus/`
  with `small` ≈ 20k documents (a laptop, under a minute), `medium` ≈ 200k, `large` ≈ 1M+.
- **Comments that explain choices, not mechanics.** Where a distribution or a rate was
  chosen rather than derived, say so in a comment. The report will need to state which
  numbers are assumptions, and it must not have to reverse-engineer them from the code.
- No network access at generation time, no external data downloads.

### Compatibility with the existing repository

The generator must be usable behind this adapter interface, because existing code depends
on it:

```python
@dataclass
class Document:
    doc_id: str
    record_type: str        # one of the five in §2
    site: str
    period: str             # "YYYY-MM"
    rows: list[dict]
    label: int              # 0 clean, 1 anomalous
    anomaly_kind: str | None
    anomaly_row: int | None

class DocumentGenerator:
    def __init__(self, seed: int = 7, anomaly_rate: float = 0.04): ...
    def generate(self, n_docs: int) -> list[Document]: ...
    def generate_of_kind(self, kind: str | None, n: int) -> list[Document]: ...
```

Keep these names and signatures working — as a thin adapter over the real generator if the
internal design is richer, which it should be. Extra fields on `Document` are fine; missing
ones are not.

---

## 10. The data card

A `data_card.md` that states, in plain language and without hedging:

- Everything here is invented. No factory, worker, buyer, auditor or document is real.
- The anomaly rate, the attack rates and the site characteristics were **chosen, not
  observed**, and no claim is made that they resemble the real industry.
- What the corpus can support: comparing methods against each other under identical
  conditions.
- What it cannot support: any statement about the prevalence of fraud in Bangladeshi
  garment manufacturing, or any accuracy claim transferable to real documents.
- The known ways this corpus could flatter a detector — for example, if a summary statistic
  turns out to carry most of the signal, a method built on summaries will look good for
  reasons that have nothing to do with the method. Say so explicitly, and suggest the test
  that would reveal it.

Write it as though a hostile reviewer will read it looking for overstatement, because one
will.

---

## 11. Acceptance tests to include in the package

Ship these as `tests/` and make them pass:

1. Same seed twice → identical file hashes for every output file.
2. Different seed → different content, same schema, and label rates within 10% of target.
3. Every document validates against its record type's schema; every declared anomaly row
   index is in range.
4. Anomaly rate, per site and per wave, is within tolerance of the configuration.
5. The Dirichlet partition is reproducible and genuinely non-IID — report the per-site
   anomaly-kind distributions and assert they differ.
6. Benchmarks are disjoint from training shards, by document id.
7. Every event in the adversary trace resolves to documents that exist in the corpus, and
   every withheld document is absent from the disclosed set and present in the full set.
8. `cross_inconsistency` and `cross_document_fraud` cases are **not** detectable from the
   single document alone — assert that the falsified document is internally consistent.
9. Streaming a `large` corpus stays under a stated memory ceiling.
10. A trivial baseline (logistic regression on a handful of obvious features) reaches
    somewhere well short of perfect on the realistic mix. If it scores 99%, the corpus is
    too easy and the generator needs to say so loudly rather than let us publish it.

Test 10 matters more than it looks. A synthetic corpus that a trivial model solves makes
every subsequent result meaningless, and it is the first thing a reviewer will try.

---

## 12. What to hand back

1. The package, complete and runnable.
2. A short `README.md`: how to run it, what each output file contains, and how long each
   scale takes.
3. The `data_card.md`.
4. A note listing every design decision you made that this prompt left open, and what you
   chose. That note is more useful than any amount of polish, because it is what we will
   need to defend.
