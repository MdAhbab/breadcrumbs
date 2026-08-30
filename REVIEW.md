# Adversarial Review Log — Breadcrumbs

This file records what a deliberately hostile expert reviewer threw at the
submission, and exactly what we changed in response. It is kept separate from
`main.tex` so the team can read the attacks and the answers side by side before
walking into a judging room.

**Method.** A reviewer persona was written first
(`.claude/skills/hardball-reviewer/SKILL.md`) and instructed to reject by
default: find the load-bearing claim and test it, delete each technology in turn
and ask what is lost, treat every unsourced number as fabricated, assume every
participant is rational and self-interested, and check every citation against
the real source. That reviewer was run as an independent agent with no access to
our reasoning, only to the document and the code. It was given permission to run
our experiments and try to break them.

One full round is recorded below, and it changed the method itself. A second
round was attempted four times and never completed; that is documented honestly
further down rather than papered over.

---

## Round 1 — verdict: **major revision**

The reviewer's summary was that the idea was sound and the engineering honesty
was above competition standard, but that three things would kill it in the room:
a regulatory claim falsified six days before the date we cited, three
bibliography entries with fabricated co-authors, and a simulation whose own code
showed one of our three named mechanisms made the system worse.

Every finding below was independently re-verified by us before we acted on it.
All of them held.

---

### K1. "Your Executive Summary says the EU's high-risk AI rules became applicable on 2 August 2026. The Digital Omnibus deferred exactly those obligations to December 2027, six days before the date you cite. Which of your three deadlines is still real?"

**Status: confirmed. We were wrong.**

Regulation (EU) 2026/1744 was published in the Official Journal on 24 July 2026
and entered into force on 27 July. It defers Annex III standalone high-risk
obligations to **2 December 2027** and Annex I embedded systems to **2 August
2028**. Only the Article 50 transparency duties still applied on 2 August 2026.

A second error rode along in the same sentence: we had written that Article 12
requires *tamper-evident* logging. It does not. It requires automatic event
logging. We had manufactured a blockchain requirement the law does not create.

**What we changed.** Section 2.1 now states the deferral, the new dates, and the
fact that Article 50 was not deferred. The tamper-evidence claim is deleted and
replaced with an explicit disclaimer: *"It requires logging; it does not require
that the log be tamper-evident, and we do not claim otherwise."* The Executive
Summary carries the corrected date. `eu2026aiomnibus` was added to `ref.bib`.

The argument survives the correction, and is arguably stronger: the obligations
are still coming, and a system being designed now should be built for them.

---

### K2. "All three of your federated-continual-learning surveys have invented co-authors. Did you read the papers your novelty claim rests on?"

**Status: confirmed. This was the most serious finding, and the fault was ours.**

Three entries had correct first authors, correct titles, correct venues,
volumes and article numbers, and **wrong co-authors**:

| Key | What we had written | The actual co-authors |
|---|---|---|
| `gholizade2026fcl` | Soltanizadeh, Rahmanimanesh, Sana | Ruffini, Ducange, Marcelloni |
| `hamedi2025fcl` | Kazemi, Rahmani | Razavi-Far, Hallaji |
| `wang2024fcledge` | Zhang, Wu, Zhang, Chen, Ren | Wu, Yu, Zhou, Hu, Min |

The cause was a verification script that printed only `FirstAuthor (+N)`. The
remaining names were then filled in from memory rather than fetched. That is
fabrication, and the fact that it was careless rather than deliberate does not
change what it would look like to an academic judge. It was worse for being
under a header claiming the references had been verified.

**What we changed.** All three entries corrected from the arXiv API. A full
author-level audit was then run over **every** entry in `ref.bib`, comparing our
complete author list against arXiv and Crossref. The only remaining flag is
arXiv parsing "Agüera y Arcas" as the surname "Arcas", where our form is the
correct one. The header comment in `ref.bib` was rewritten to describe what was
actually done.

---

### K3. "Table 4 has no replay-only row. I ran your code with the Fisher penalty off. Replay alone beats your hybrid. Why is Fisher in the paper?"

**Status: confirmed. This changed the method.**

We had never run the ablation. When we did, over five seeds:

| Variant | Average accuracy | Forgetting |
|---|---|---|
| Prototype replay only | **77.9** | 7.6 |
| Fisher + replay (our proposed "hybrid") | 74.0 | 6.5 |

The Fisher penalty bought 1.1 points of forgetting and cost 3.9 points of
average accuracy, and 9.2 points on the newest stage. We extended the difficulty
sweep to seven settings: replay-only has the higher average accuracy at **every
one**.

Worse, this falsified a set-piece we were proud of. We had written that being
weaker on the newest task was "the stability and plasticity trade-off, and not a
bug we intend to hide". It was not an inherent trade-off at all. It was our own
component, and deleting it recovered most of the loss.

**What we changed.** The Fisher penalty was **removed from the method**. Section
6 is now "Our two mechanisms, and one we removed". Section 7.1 reports the
ablation against ourselves. Headline numbers improved: 77.9 / 7.6 replaces
74.0 / 6.5, now 3.1 points from the centralised ceiling instead of 7.0. The
architecture diagram, the on-chain/off-chain table, the glossary and the
14-week plan were all updated for consistency.

---

### K4. "I took your memory bank, threw away the federated learning entirely, trained one model centrally on synthetic data alone, and it beat your full system. What is the federated learning for?"

**Status: confirmed, and we could not fix it.**

A model trained only on synthetic records drawn from the memory bank, with no
federated training, no rounds and no continual learning, scores **77.4** against
our 77.9. The reviewer's diagnosis was structural: our synthetic classes are
Gaussian blobs, and `build_prototypes` summarises each class as cluster centres
plus a diagonal variance, which is very nearly a sufficient statistic for the
data-generating process. The benchmark cannot separate "prototype replay works"
from "we chose data our summary reproduces exactly".

**We tried to rebut this and failed.** We rebuilt the generator so features are
correlated (random orthogonal mixing), skewed and heavy-tailed, specifically so
that a diagonal-Gaussian summary would no longer be sufficient. The probe still
matched us: 78.1 against 79.0.

**What we changed.** We report it. Section 7.3 is titled "A test our own
benchmark fails" and states plainly that the learning claim in this report
should be read as a mechanism behaving as designed on synthetic data, not as
evidence about real documents. The probe is shipped as a runnable script
(`prototype/probe_sufficiency.py`) so anyone can reproduce it. We also drew the
one conclusion that cuts in our favour and stated it: if the summaries are that
informative, they leak more than we assumed, which raises the priority of the
privacy work rather than lowering it.

---

### K5. "IBM holds US 11,157,833, in which a smart contract tests a model against hidden test data and a performance threshold. Your Continuity Gate is that. What exactly is new?"

**Status: confirmed. The novelty claim was too broad.**

We had twice written unqualified negatives: "we have found no system in which
the continual learning memory and the decision to accept a new model version are
themselves governed by smart contract". Prior art the reviewer surfaced:

- **US 11,157,833 B2** (IBM, granted October 2021) — on-chain accuracy gate
  against a withheld test set. Also a freedom-to-operate question, not only a
  novelty one.
- **LiFeChain** (arXiv 2509.01434) — blockchain for federated *lifelong*
  learning with on-chain verification.
- Ordinary MLOps model registries already apply accuracy gates before release.

**What we changed.** Section 4.1 now names all three and states the difference
precisely instead of claiming a clean field. What survives is narrower and
defensible: a promotion rule that is **backward-looking over a set of per-task
benchmarks whose hashes were committed before the round, enforced by a threshold
of independent organisations rather than by one owner**. The comparison table
gained a "Gate on past tasks" column and rows for notarisation services, the IBM
patent, LiFeChain and MLOps registries. Section 11 answers the patent question
directly and says a team taking this to market would need legal advice.

---

### Substantive problems also fixed

**The gate could not have run as drawn.** Chaincode must be deterministic across
endorsing peers, and a floating-point neural forward pass is not; and the
contract cannot evaluate a model whose weights Table 2 deliberately keeps
off-chain. Algorithm 1 was redesigned: endorsers evaluate off-chain against the
hash-committed benchmark and **sign** their metrics, and the contract checks the
signed values agree within a tolerance before applying the threshold rule. The
guarantee is now stated exactly, and it is slightly weaker than "computed
on-chain".

**Benchmark gaming.** A fixed, known benchmark is a target. Benchmarks are now
contributed by a rotating subset of members, hash-committed before the round and
revealed only after promotion, so those training in a round do not hold the set
they will be judged against. We state that this does not eliminate the risk, it
converts it into one requiring collusion.

**Three privacy mechanisms that cannot coexist.** Secure aggregation hides
individual updates; trimmed mean requires ranking them; contribution scoring
requires attributing them. Section 5.2 now declares the conflict and picks two,
giving up secure aggregation in the first deployment, and says so in the
limitations.

**"Differential privacy" without a budget.** We had no sensitivity bound and no
stated epsilon, and were releasing per-class variances and counts entirely
unnoised. The document now calls it what it is, "noised aggregate summaries",
and specifies what making it real would require.

**Chance accuracy was never stated.** Each stage's test set has two classes, so
chance is 50 percent, which means the baseline's 45.2 is *below chance* and
"60.0 average" means "barely better than a coin flip". Chance is now stated in
the text, given its own row in Table 4, and drawn as a dashed line on Figure 3.

**Forgetting of 0.0 for centralised pooling was definitional, not measured** (it
never trains sequentially). Marked `n/a`.

**The conclusion attributed the result to the blockchain.** The simulation
contains no ledger and no gate. The conclusion now separates measured from
designed and says so explicitly.

**The audit-savings arithmetic did not close.** Two avoided audits at $800 is
$1,600 against a $2,400 year-two fee. Section 9 now states the shortfall, refuses
to fix it by inventing a higher audit price, and names the real binding
constraint: no buyer has agreed to accept cryptographic evidence instead of a
visit, and under CSDDD liability their first instinct is to audit *more*.

**The HRW citation did not support the claim it was attached to.** HRW documented
auditors recycling stock language and skipping questions, which is a finding
about auditor effort, not about tampered documents. Section 2 now cites it only
for what it shows and states plainly that we have no published measurement of
how often records are altered, only that nothing prevents or reveals it.

**Difficulty tuning was undisclosed**, and 0.50 is close to the value that
maximises the baseline's forgetting. Section 7.2 now discloses this, and Table 5
shows all seven settings including the range above 1.00 where the forgetting
problem largely disappears without our machinery.

**CSDDD scope.** The 2026 omnibus cut it to companies above 5,000 employees and
EUR 1.5bn turnover. Added, because it means far fewer buyers are in scope than
the original directive implied.

**Also:** an unused reference pointing at a bare homepage was deleted; an
unmeasured "under a second" timing claim was removed from a figure caption; the
LDC hedge from Section 2.1 was carried into the Executive Summary.

---

## Round 2 — not completed

Four attempts were made to run a second independent review of the hardened
document. All four terminated early for infrastructure reasons rather than
because they found nothing: one hit an account session limit, one stalled, and
two failed on server overload errors. Two of them got far enough to report
partial results before dying, and those partial results are recorded here
because they are still evidence:

- One confirmed that **Table 4 reproduces exactly** from `fcl_sim.py`.
- One reported it was mid-way through checking the bibliography and the
  sufficiency probe when it stopped.

**This section is therefore incomplete, and the submission has had one full
adversarial review, not two.** We would rather state that than imply a clean
second pass we did not get. If the team can run another before the deadline, the
prompt used is worth reusing: give a fresh agent the persona file, the document,
the code, and instructions to verify facts independently and try to break the
experiment.

### What we audited ourselves instead

Not a substitute for an independent reviewer, and we do not present it as one.
These are mechanical checks, which is precisely what a self-review is good for
and what it is not. Each one found something:

1. **Every number in the prose traced back to a data file.** A script pulled
   every decimal figure out of the body text and checked it against
   `fcl_results.json` and `sweep_results.json`. Two numbers (78.1 and 79.0, from
   the hard-data probe) were not traceable to any file, because the probe printed
   to the terminal without saving. `probe_sufficiency.py` now writes
   `probe_results.json`, so all three tables and every quoted figure resolve to
   a file on disk.
2. **The two derived comparisons check out**: 77.9 minus 74.0 is the 3.9-point
   accuracy cost of the Fisher penalty, 7.6 minus 6.5 is the 1.1-point forgetting
   gain, and 79.9 minus 70.7 is the 9.2-point cost on the newest stage.
3. **The removed mechanism left stale traces.** The architecture figure still
   read "Secure aggregation with noise" in the learning plane, contradicting
   Section 5.2, which now says we give secure aggregation up in the first
   deployment. Found only because the figures were exported standalone and looked
   at as images. Corrected to "Robust aggregation, clipping and noise".
4. **A contradiction inside the hard-questions section.** The answer on gradient
   inversion still promised "secure aggregation so no individual update is
   readable" and "noise with a stated budget", both of which the revised
   Sections 5.2 and 12 say we do not have. Rewritten to match.
5. **Two sweep figures were quoted in reverse order** in Section 7.2 (the Fisher
   penalty's 46.8 against the baseline's 50.1 had been written the other way
   round, which inverted the point being made).
6. **Section cross-references had gone stale** after subsections were added and
   removed. All hardcoded "Section 7.2"-style references in the report were
   converted to real LaTeX labels, and the companion files corrected. All 26
   labels now resolve with no undefined references.
7. **Sentence length regressed during compression.** Trimming reintroduced three
   sentences over forty words, against the project's own style rule. Split.
8. **A claim of "three parts"** was followed by text that did not enumerate
   three. Reworded.

None of these change a conclusion. They are the class of error that accumulates
when a document is revised heavily and quickly, which is exactly why the checks
were run mechanically rather than by re-reading.

---

## Two questions we answer here rather than in the report

These are questions about our *process* rather than about the system, so they
live here instead of taking space in `main.tex`. Expect them anyway.

**"You removed one of your own mechanisms after testing it. Doesn't that show
the design was guesswork?"**
It shows we tested it. The first version proposed a Fisher penalty alongside
replay because both are standard and the combination sounded reasonable. The
ablation showed the penalty cost 3.9 points of accuracy and bought 1.1 points of
forgetting, so we removed it and rewrote the claim it had supported. A design
that has survived an ablation is worth more than one that has never had one. The
alternative was to keep a component we had measured as harmful because three
mechanisms sound better than two.

**"Your own probe shows a model trained on synthetic summaries alone does as
well as your whole system. Why do you need the federated learning?"**
The result is real and it is in Section 7.3 of the report. It reflects the
benchmark rather than the architecture: our synthetic categories differ mainly
in their average feature values, so a summary of those averages carries most of
the signal, and making the data correlated and heavy-tailed did not change it.
The conclusion is that only real documents can validate the learning claim, not
that the architecture is wrong. It also cuts the other way: summaries that
informative leak more than we assumed, which raises the priority of the privacy
work rather than lowering it.

---

## What we did not change, and why

**We did not remove the self-criticism to make the pitch cleaner.** Sections 7.2,
7.4 and 12 make the document harder to read and easier to attack on a first
pass. They also mean that the obvious attacks are already answered in writing. A
judge who finds a weakness we have already stated is a judge we are having a
conversation with, not one who has caught us.

**We did not restore the Fisher penalty**, even though "three novel mechanisms"
sounds better than two. It measurably made the system worse.

**We did not soften the sufficiency probe.** It is the single most damaging
result in the report and we could not overturn it. Hiding it would have been the
one finding that, if discovered by a judge, would call everything else into
question.

---

## How to use this file

Before a presentation, read the five kill shots above out loud and answer them
from memory. If you cannot, the answer is in the section of `main.tex` named in
each response. The questions a real judge asks will be drawn from the same pool,
because these were generated by a reviewer told to end the pitch.
