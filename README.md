# Breadcrumbs — Blockchain Olympiad submission

Team CookieMonsters, United International University.

**One line:** a permissioned blockchain that makes a garment factory's own
internal records provable without publishing them, plus a shared fraud detector
that many factories train together without handing over data, governed by a
smart contract that refuses a new model version if it has forgotten what the
network already knew.

---

## What to submit

Upload **two files** to Overleaf and compile with **pdfLaTeX**:

```
main.tex
ref.bib
```

That is everything. Every figure and the logo are drawn in TikZ inside
`main.tex`, so there are no images to upload and nothing can go missing.
Overleaf runs BibTeX automatically.

Verified locally with Tectonic 0.17: no errors, no undefined references, no
overfull lines, no sentence over 40 words.

**Before submitting**, edit the team block at the top of `main.tex` (lines 15
to 21) and replace the two bracketed placeholders:

```latex
\newcommand{\TeamMembers}{[MEMBER 1], [MEMBER 2], [MEMBER 3]}   % <-- fill in
\newcommand{\TeamContact}{[TEAM EMAIL ADDRESS]}                 % <-- fill in
```

---

## Folder contents

| Path | What it is |
|---|---|
| `main.tex` | The report. Single column, 6,820 words of prose plus tables and figures. |
| `ref.bib` | 53 references. Every author list fetched from a primary source, not written from memory. |
| `figures/` | The four figures exported standalone as `.tex`, `.pdf` and 300 dpi `.png`, for slides and posters. Not needed to compile the report. |
| `Breadcrumbs Project/` | The working system: `model/` (permissioned ledger, chaincode, Merkle, federated learning), `backend/` (FastAPI), `frontend/`, `deck/`. |
| `Breadcrumbs Project/model/experiments/` | The simulation behind Table 4, Table 5 and Figure 3, plus the self-test that went against us. |

Reproduce every number in the report:

```bash
cd "Breadcrumbs Project/model/experiments"
python3 fcl_sim.py           # Table 4 and Figure 3
python3 sweep_difficulty.py  # Table 5
python3 probe_sufficiency.py # the test in Section 7.3 that we failed
```

Each writes a JSON file next to it (`fcl_results.json`, `sweep_results.json`,
`probe_results.json`). Every number in the report traces back to one of those
three files.

NumPy is the only dependency. Everything runs in under a minute.

---

## Where the answers live

| A judge asks | Section |
|---|---|
| Why not just a database? | §3, Table 2, and §11 |
| What is the energy cost? | §3, on ordering-based consensus |
| BGMEA already signed two blockchain deals. Why do you exist? | §4 and §11 |
| Isn't this federated learning with a ledger bolted on? | §4.1 |
| IBM has a patent on on-chain model gating. | §4.1 and §11 |
| Your chain records a lie perfectly. So what? | §11, first question |
| Did you tune the experiment to win? | §7.2 and Table 5 |
| What can't you do? | §12 |

---

## Know these before you present

These are all stated in the report. Do not be surprised by them on stage.

1. **The results are a simulation on invented data.** Not real factory
   documents. Never let anyone summarise it as "we measured 77.9 percent
   accuracy in factories".
2. **Chance accuracy is 50 percent**, because each stage's test set has two
   categories. The meaningful band runs 50 to 81, not 0 to 100. The baseline's
   45.2 is *below* chance.
3. **The Continuity Gate, our main contribution, is specified but not built.**
   No accuracy number in the report involves a ledger.
4. **We removed one of our own mechanisms** after an ablation showed it cost 3.9
   points of accuracy. The method changed during the work. That is a strength,
   not an embarrassment: say so.
5. **Our benchmark cannot validate the learning claim.** A model trained only on
   synthetic summaries matches our full system, and making the data harder did
   not change it. Section 7.3.
6. **Audit costs are vendor list prices** and the revenue model is an assumption
   set. The audit saving does not fully cover the subscription, and the report
   says so.

---

## How the references were checked

Nothing was cited from memory. arXiv entries were resolved through the arXiv
API and journal entries through Crossref by DOI, in both cases fetching the
**complete** author list rather than the first author. EU instruments were
checked on EUR-Lex. Bangladesh sector data comes from BGMEA's published export
page. A full author-level audit was re-run over every entry after an earlier
draft was found to contain three fabricated co-author lists.

Last audit: 14 August 2026.
