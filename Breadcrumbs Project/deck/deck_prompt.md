# Deck prompt — paste this whole file into PowerPoint Copilot

Everything below the line is the prompt. Paste it as one message.

---

You are building a 15-slide keynote presentation in PowerPoint. Work like a
senior presentation designer at an agency that builds Apple keynotes — not like
a template filler. Use GPT Image 2 for every image and infographic described.

## Non-negotiables

1. **Never more than 18 words of body text on a slide.** If an idea needs more,
   it needs another slide or it belongs in the speaker notes. Write full speaker
   notes for every slide; that is where the detail lives.
2. **No bullet points anywhere.** Use one large statement, a figure, a diagram,
   or a two-column comparison. If you feel the urge to make a bulleted list,
   make a diagram instead.
3. **No stock-photo clichés.** No handshakes, no globes with glowing lines, no
   people in hard hats pointing at tablets, no chain-link or floating-cube
   blockchain imagery, no circuit-board brains. These read as filler and a judge
   will discount everything near them.
4. **One idea per slide.** The title states the idea as a claim, not a category.
   "The gate refused it" — not "Continuity Gate Overview".
5. Text must clear all imagery. Where an image sits behind type, add a solid or
   gradient scrim so contrast stays above 4.5:1. Never let type fight a photo.

## Visual system

- **Palette.** Deep indigo `#1E2A44` as the dominant dark ground. Warm off-white
  `#EDEAE0` for light slides. Brass `#B08A3E` as the single accent — use it for
  one element per slide and no more. Green `#2E6B5E` for verified and promoted,
  rust `#9C4A34` for rejected and failed. Never use brass for body text.
- **Type.** Fraunces Semibold for slide titles (or Playfair Display if Fraunces
  is unavailable). Inter for body. IBM Plex Mono for hashes, identifiers and any
  number that is evidence. Titles 40–54pt, body 20–24pt, never below 18pt.
- **Layout.** Alternate deliberately between full-bleed dark image slides and
  quiet light data slides, so the deck has rhythm. Break the centre: place
  titles on a left third with the figure occupying the right two-thirds more
  often than you centre them.
- **Depth, used with restraint.** Real 3D extrude and bevel on the ledger-block
  objects in slides 4, 7 and 8 only, lit from the upper left with a soft shadow.
  Everything else stays flat. Depth applied everywhere reads as clip art;
  applied to one recurring object it reads as a motif.
- **Transitions.** Morph between slides 6→7→8, so the block objects travel and
  the audience follows one continuous idea. Simple Fade elsewhere. No wipes, no
  cubes, no page curls.
- **Build order.** On the two data slides that carry a verdict (7 and 8), animate
  the table rows in first and the verdict banner last, so the audience reads the
  evidence before the conclusion.

## Framing — read this before writing a word

This is a **blockchain** entry, not an AI entry. The ledger is the product; the
machine learning is a tool the ledger governs. If a slide makes the AI the hero,
it is wrong.

The team's credibility comes from disclosing limitations, not hiding them.
Slide 13 is not a weakness — it is the strongest slide in the deck and should be
designed with as much care as the hero. Judges have seen fifty decks that claim
everything works. They have not seen one that says what does not.

Never claim the system was measured on real factory data. It was not. Every
number comes from a simulation on invented data, and the deck says so on the
slide where numbers first appear.

---

## The 15 slides

### 1 — Title
**Breadcrumbs**
Subtitle: "Prove one line. Reveal nothing else."
Team CookieMonsters · United International University · Blockchain Olympiad 2026 Finals

*Image:* full-bleed dark indigo. A woven textile macro, extremely close, so the
warp and weft read as a grid — dissolving on the right third into a fine grid of
hexadecimal characters in brass. The metaphor is the whole product: cloth
becoming record. No logo lockups, no gradients.

*Notes:* one sentence of what it is, one of who it is for, then move on. Do not
read the title aloud.

### 2 — The problem, in one number
Headline: **"An audit copies the whole file to prove one line."**
Below: the single figure **1,847** with the caption "rows handed over to verify one."

*Image:* a photographic stack of printed payroll registers, shot from a low
angle so the stack towers, lit warm from one side against a dark ground. One
sheet glows brass. Everything else is in shadow.

*Notes:* Bangladesh's ready-made-garment sector is roughly 84% of exports. A
buyer asking whether one worker was paid legally currently receives the entire
register — or a PDF nobody can check. Both are bad answers.

### 3 — Why anyone should trust a shared record
Headline: **"Nobody here can be the custodian."**
Four short labels around a centre: Factory (presents its own records) · Buyer
(shifts liability, controls the orders) · Auditor (paid by the inspected) ·
Regulator (arrives afterwards).

*Infographic:* four nodes in a ring, each with a small icon, all connecting to a
central empty slot marked with a brass dashed outline and the words "no neutral
party". Flat, precise, generous whitespace, light background.

*Notes:* this is the Wüst–Gervais test — multiple writers, mutual distrust, no
trusted third party. All three hold, which is what justifies a blockchain here
and what most proposals in this category cannot honestly claim.

### 4 — What goes on the chain, and what never does
Two columns, dark slide.
**On-chain:** root hashes · metadata · access grants · model decisions
**Never on-chain:** the document · worker names · wages · national IDs · model weights

*Infographic:* a 3D ledger block on the left, extruded, brass-edged, containing
small hash glyphs. On the right, a document icon behind a solid wall, with a
green tick meaning "stays here, and stays deletable".

*Notes:* an append-only ledger and a right to erasure cannot both hold for the
same bytes. So the bytes that must be erasable never go on the ledger. This is
also the answer to "why not just a database" — the chain holds commitments and
decisions, which is exactly what a database cannot make credible between
distrusting parties.

### 5 — Selective disclosure
Headline: **"One row. Eleven hashes. Nothing else moves."**

*Infographic — the deck's most important diagram.* A Merkle tree of eight
leaves. One leaf is brass and labelled `net_pay_bdt = 14,820 BDT`. The path from
that leaf to the root is drawn in solid brass; the eleven sibling hashes on the
path are shown as short mono strings. Every other leaf is drawn as a redacted
grey bar with no readable content. At the root, a small green `MATCH` badge.

*Notes:* the buyer recomputes the root from the disclosed row and the siblings,
and compares it to the root already committed. The other 1,846 rows are never
transmitted and cannot be recovered from the proof. Salted per row, so guessing
a neighbouring value does not work either.

### 6 — The shared detector
Headline: **"Six factories train one model. No data moves."**

*Infographic:* six factory silhouettes around a central model glyph. Arrows from
factories to centre are labelled "model updates only" in mono. Arrows are
brass; a dashed red line crossing a "raw records" arrow shows what never
happens.

*Notes:* federated learning, clipping and noise on every update, trimmed-mean
aggregation so one dishonest participant cannot move the model. Be honest: we
do not run secure aggregation in the first deployment, because it cannot coexist
with contribution scoring and robust ranking. We chose which two of the three to
keep and we say so.

### 7 — The problem nobody else is checking
Headline: **"A model that improves can still be getting worse."**

*Table, three rows.* Wage-register inconsistency 91.6% → 73.5% (rust, down
arrow) · Forged certificate 97.8% → 100.0% (green) · Chemical misreporting
48.0% → 100.0% (green).
Caption beneath in brass: "Best model yet at the newest problem."

*Notes:* forgetting does not make an update look bad. On the data a reviewing
committee is looking at, it looks excellent. That is why committee validation
and ordinary MLOps gates miss it — they are all looking forward.

### 8 — The Continuity Gate refuses it ★
Headline: **"The contract said no."**
Full-bleed dark. A large rust-coloured **REJECTED** banner. Beneath it, in mono:
`accuracy on wage_register_inconsistency fell by 1805 bp, tolerance is 500 bp`.
Small line at the bottom: "Endorsed by 3 of 5 organisations · recorded in block."

*Image:* the 3D ledger block from slide 4, now with a rust seal across its face.
Morph from slide 7 so the table shrinks into the block.

*Notes:* **this is the moment to slow down.** A candidate is promoted only if it
improves on the new task *and* has not lost more than an agreed tolerance on
every earlier one, each measured against a benchmark whose hash was committed
before the round began. The gate is enforced by chaincode, so no single
participant — including whoever ran the training — can overrule it. Rejections
are recorded as permanently as promotions.

### 9 — How it stays honest
Headline: **"The exam is sealed before anyone studies."**

*Infographic:* a timeline. `Benchmark hash committed` → `Round opens` →
`Factories train` → `Endorsers evaluate and sign` → `Contract decides` →
`Benchmark revealed`. A padlock sits on the first node and opens on the last.

*Notes:* a fixed, known benchmark is a target — a participant that wants its
model promoted can train on it. Contributed by a rotating subset, committed by
hash, revealed only after the decision. Say the limitation plainly: this does
not eliminate the risk, it converts it from something one member can do quietly
into something requiring collusion.

### 10 — What we actually built
Headline: **"It runs."**
Four figures across: **69** tests passing · **2** channels · **3** chaincodes ·
**50,000** generated documents.

*Image:* a clean screenshot of the terminal demo output showing the REJECTED
banner and the per-task table, on a dark ground with a subtle brass border.

*Notes:* a permissioned ledger with X.509 identities, endorsement policies that
count organisations rather than signatures, Raft-style ordering, MVCC validation
and hash-chained blocks. Plus the same three contracts ported to real
Hyperledger Fabric. Tamper with any committed block and the chain fails
verification — there is a button in the product that checks.

### 11 — Where we sit
Headline: **"We lose most of these columns. We only need the last one."**

*Table.* Rows: TextileGenesis / TrusTrace · AWARE & DigiProd Pass (BGMEA) ·
Guardtime & OpenTimestamps · Swarm Learning · LiFeChain · IBM US 11,157,833 ·
**Breadcrumbs**. Columns: Ledger · Internal records · Shared model · Learns over
time · **Gate on past tasks**. Dashes everywhere they belong. Only the final
column and the final row are highlighted in brass.

*Notes:* name what we do not beat. Notarisation already makes documents
tamper-evident. LiFeChain already puts federated lifelong learning on a chain.
IBM holds a patent on on-chain threshold checks against a withheld test set, and
any team building this would need advice on it. Our narrow claim: a promotion
rule that is *backward-looking* over pre-committed per-task benchmarks and
enforced collectively.

### 12 — Where it fits the industry
Headline: **"Underneath the passport, not against it."**

*Infographic:* a layered stack. Top: "Digital Product Passport (BGMEA + AWARE,
May 2026)". Bottom, in brass: "Breadcrumbs — the internal evidence that makes
its claims worth believing."

*Notes:* BGMEA signed two blockchain traceability agreements — DigiProd Pass in
May 2025 and AWARE in May 2026. That is the strongest evidence in our submission
that the demand is real, and it means competing with them would be unwise. Those
systems answer "where did this cotton come from". They say nothing about whether
the factory's own wage register is authentic. A passport asserting legal wages is
only as good as the record behind it.

### 13 — What we cannot do yet ★
Headline: **"What we cannot do yet."**
Light slide, generous space, five numbered lines in restrained type — no icons,
no colour coding, no attempt to soften it:
1. Every result is a simulation on invented data. Not a measurement of any factory.
2. Our own benchmark cannot validate the learning claim — a model trained on
   summaries alone matched the full system.
3. Our added noise is not differential privacy. No sensitivity bound, no budget.
4. Secure aggregation, robust averaging and contribution scoring cannot all
   three hold. We gave up the first.
5. A signed record of a false statement is still a correct record of a lie.
   The first-mile problem is mitigated, not solved.

*Notes:* say "we removed one of our own mechanisms after measuring that it cost
3.9 points of accuracy". Do not apologise for this slide. Every other team will
claim their system works perfectly; the panel will believe whoever shows they
looked for the holes themselves.

### 14 — What happens next
Headline: **"A pilot turns every simulated number into a measured one."**

*Infographic:* three phases on a horizontal track — "Pilot with one factory
under NDA" · "Extend to a buyer and an auditor" · "Consortium governance with
BGMEA". Each with one line beneath. Brass progress rule beneath the first.

*Notes:* infrastructure is roughly $60–120 per peer per month at published list
prices — not a measured operating cost. The audit saving does not fully cover a
subscription on our own assumptions, and the model depends on buyers accepting
cryptographic evidence, which none has yet agreed to do.

### 15 — Close
Single line, centred on deep indigo: **"Prove one line. Reveal nothing else."**
Small beneath: the repository URL and the team name.

*Image:* the woven-textile macro from slide 1, reversed — hexadecimal resolving
back into cloth. Bookends the deck.

*Notes:* one sentence. Stop talking. Take questions.

---

## Speaker notes: rehearse these three answers

**"Why not just a database?"** Slide 3 and 4. Four parties, mutual distrust, no
candidate custodian. And we keep almost everything off the chain — it holds
commitments and decisions, not data.

**"Your chain records a lie perfectly. So what?"** Correct, and named on slide
13. What changes is that the lie becomes attributable, timestamped, and
impossible to revise quietly afterwards. That is a smaller claim than "we stop
fraud", and it is one we can defend.

**"Isn't this federated learning with a ledger bolted on?"** No — the ledger
decides what the learning is allowed to publish. Remove the chain and the
Continuity Gate becomes a promise from whoever runs the server, which is exactly
the thing it exists to replace.
