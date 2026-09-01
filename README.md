# Breadcrumbs

**A permissioned blockchain that proves nothing is missing.**

Blockchain Olympiad Bangladesh submission · Team CookieMonsters · United International
University, Dhaka.

---

## The idea in one paragraph

Bangladesh exports about 39 billion dollars of clothing a year, and every shipment rests on
paperwork a buyer does not trust: wage registers, safety inspections, chemical inventories.
So buyers send auditors instead, factories pay for audit after audit, and the documents
behind them can still be edited afterwards.

Breadcrumbs makes a factory's own internal records provable without publishing them. Only
commitments go on the chain; the files stay in the factory. But the part we would defend
hardest is not that a document can be proved genuine — notarisation services have done that
for years. It is that a factory can be made to prove **nothing is missing**.

Every provenance system on the market answers *"is this document real?"*. None answers *"is
this every document, and was anything withheld?"* — which is the question that matters,
because the fraud that actually happens is not a forged register but a second one and a
decision about which to show.

## What that looks like

A factory hands a buyer four payroll registers. All four are genuine. Every hash matches,
every Merkle proof verifies. Every comparable system reports success.

Breadcrumbs closes a reporting period into a **seal**: the contract enumerates every record
the ledger holds for that site, type and period, refuses to close unless the declaration
matches, and commits a count and a root. The buyer recomputes and the arithmetic does not
add up. One register is missing, and nobody had to be trusted to notice.

```bash
cd "Breadcrumbs Project" && make setup && make demo   # watch Act 6
```

## Four mechanisms, one piece of mathematics

RSA gives a *group of unknown order*. That single object does four jobs, which is why RSA is
here rather than a faster signature scheme:

| | |
|---|---|
| **Membership witnesses** | The whole record set commits to one number. A verifier holds 384 bytes instead of a copy of every commitment. |
| **Non-membership witnesses** | "No such certificate was ever committed" becomes cryptographic evidence rather than a filing failure. A Merkle tree cannot answer this at any price. |
| **Batching proofs** | An epoch of any size verifies in ~9 ms. Measured at 500 records: **403× faster** than recomputing, and flat as the count grows. |
| **A delay function** | Hash chains prove order, not duration. This stops a colluding majority manufacturing months of history over a weekend. |

Beside them sits the answer to the limitation every system of this kind concedes and none
solves — that a ledger makes a record unchangeable but says nothing about whether it was
true when written. Each record is counter-signed by a second organisation that is
**assigned, not chosen**, from a commit–reveal seed no single member controls, and that
loses more than four times what honest attestation earns if the record is later found false.

That does not make records true. It converts unilateral falsification into two-party
collusion that is recorded and attributable, and we say it in exactly those words.

## Three attacks in our own test suite succeed

They are in the report as successes, and `make attacks` runs them:

- A model poisoned just inside the Continuity Gate's tolerance is **promoted**. The gate
  bounds regression per round, not cumulatively.
- A colluding assigned witness is **not stopped**. Nothing in this design class can stop it.
- Whoever holds the factorisation of the accumulator modulus **can forge** a membership
  witness — against the accumulator alone. It still fails the ledger check and the anchored
  index, which is why the accumulator is an accelerator and never the authority.

A security section where everything fails is not evidence of a secure system.

## Repository

```
├── main.tex                  The report. Compiles on Overleaf with pdfLaTeX.
├── supplementary.tex         Reproduction, parameters, the full attack catalogue.
├── results.tex               GENERATED. Every measured number in the report.
├── results/                  Benchmark output as JSON, plus an index of macros.
├── ref.bib                   Bibliography.
├── figures/                  TikZ sources.
└── Breadcrumbs Project/      The system.
    ├── model/                Ledger, chaincode, accumulator, Merkle, learning plane.
    ├── backend/              FastAPI + SQLite. Wraps model/, never reimplements it.
    ├── frontend/             React + TypeScript client.
    ├── docs/                 Handoff prompts, corpus spec, future work.
    ├── AUDIT.md              Security review: findings, fixes, what is still open.
    └── SETUP.md              A fresh machine.
```

## Running it

```bash
cd "Breadcrumbs Project"
make setup      # venv, dependencies, node modules
make demo       # twelve acts, end to end, on a real ledger
make test       # 210 tests
make attacks    # only the tests that attack the system
make bench      # measure everything; regenerates results.tex
make api        # backend on :8000
make web        # frontend on :5173
```

No Docker required. The report's numbers regenerate from `make bench` — nothing in the
document is typed by hand, and an unmeasured figure renders as a bold `??` on the page.

## Honest positioning

`model/ledger/` is a permissioned blockchain written in Python, modelled on Hyperledger
Fabric's execute–order–validate architecture. **It is Fabric-modelled, not Fabric.** The same
three chaincodes are also written as real Fabric contracts in `model/fabric/` with a
docker-compose network, and no Fabric peer has ever run them. Where a number comes from the
Python chain, that is what we claim.

All learning results are on invented data, and our own probe cannot yet separate "the
mechanism works" from "this data is easy to summarise". `Breadcrumbs Project/docs/future_works.md`
sets out what closes that.

## Team

Ahbab, Ruhi, Rohan, Ishmam, Adnan — United International University, Dhaka.
