# Breadcrumbs — Design Instructions

**Paste this whole file into Claude Design / Figma Make / Claude Code.** It is the complete
specification: tokens, components, every screen, every control, and the motion design. Build
what is written here; where it is silent, follow §3.

---

## 0. Read this first — three decisions already made

**0.1 One brand, two surfaces.** There are two design languages in the repository right now:
the app portal built in Figma Make (deep slate sidebar, teal accent, Outfit/Inter/JetBrains
Mono) and the newer system spec in `breadcrumbs-figma-system.md` (loom/brass/indigo/rust,
Fraunces/Inter/IBM Plex Mono). **The second one wins, everywhere.** The portal is re-skinned
onto it. Reason: deep-slate-plus-teal is the single most over-produced palette in generated
dashboards, and this project cannot afford to look generated. The warm loom/brass/indigo
system reads as considered, editorial and institutional — which is exactly what a compliance
ledger for a regulated industry should read as.

**0.2 The epistemic stamp is the signature element.** The report's whole credibility rests
on labelling every claim by how strongly it is evidenced. That discipline becomes a visible
UI primitive — `StatusStamp` with states `measured / simulated / specified / assumption` —
and it appears throughout the product, not just in marketing. Nothing else in this category
does this. Protect it.

**0.3 Blockchain first.** This is a blockchain product in which machine learning is a
governed subject. Screens about the ledger (custody, proofs, the Continuity Gate, the block
explorer) get the strongest layouts, the most space and the best typography. ML screens are
support. Never invert this.

---

## 1. What the product is

Breadcrumbs is a permissioned ledger for Bangladeshi ready-made-garment factories. It does
three things:

1. **Makes a factory's own records provable without publishing them.** A payroll or safety
   file is hashed line by line into a Merkle tree; only the root and its metadata go on the
   ledger. A factory can later prove *one row* — one worker's net pay — and reveal nothing else.
2. **Trains a shared fraud detector across factories without moving data.** Federated
   learning; only model updates and noised summaries are shared.
3. **Governs that model with a contract.** The **Continuity Gate** refuses to promote a new
   model version that has become worse at anything the network already knew.

Five roles use it: **Factory Compliance Staff**, **Buyer / Brand**, **Auditor**,
**Consortium Administrator**, **Regulator (observer)**.

Voice: calm, plain, exact. This is evidence software. It never sells, never exclaims, never
says "revolutionary" or "trustless". A buyer reading a verification result must understand it
in five seconds without knowing what a Merkle tree is.

---

## 2. Real domain data — use these, not lorem ipsum

Every screen must be populated with this. Consistency across screens is what makes a
prototype feel real.

**Organisations and MSP identities**

| Organisation | MSP ID | Role | Country |
|---|---|---|---|
| Apex Textile Ltd | `ApexTextileMSP` | Factory | Bangladesh |
| Noor Garments Ltd | `NoorGarmentsMSP` | Factory | Bangladesh |
| Crescent Fashion Ltd | `CrescentFashionMSP` | Factory | Bangladesh |
| Primark Sourcing Ltd | `PrimarkSourcingMSP` | Buyer | Ireland |
| BV Certification | `BVCertificationMSP` | Auditor | France |
| BGMEA Consortium | `BGMEAConsortiumMSP` | Consortium | Bangladesh |
| Dept. of Labour, Bangladesh | `DOLBangladeshMSP` | Regulator | Bangladesh |

**People** — Fatema Begum (Apex Textile, factory staff) · James Holloway (Primark Sourcing,
buyer) · Dr. Meera Nair (BV Certification, auditor) · Rafiqul Islam (BGMEA, consortium admin)
· Lt. Col. (Ret.) Aziz (Dept. of Labour, regulator).

**Record types** — Payroll Register · Safety Inspection · Chemical Inventory · Machine
Maintenance · Compliance Certificate. **Schema versions** — `v2.1.0` current, `v2.0.3`,
`v1.9.0`, `v1.8.2`.

**Purpose codes** — `ETH-WAGE-VERIFY` (Ethical wage verification) · `CERT-SAFETY-AUDIT`
(Safety certification audit) · `REACH-COMPLIANCE` (REACH chemical compliance) ·
`ETH-WAGE-BATCH` (Batch wage audit) · `MACH-SAFETY-CHECK` (Machine safety check).

**Sites** — Gazipur, Ashulia, Narayanganj, Savar, Chattogram, Mirpur.

**Specimen values** — commitment IDs `rc-001`…`rc-005`; Merkle root
`a3f9e2c817b4d056f3a1e79c245b0d3f…`; block `#14,821`; disclosed field `net_pay_bdt` =
`14,820 BDT`; 1,847 rows in the July 2026 payroll register.

**Model identifiers** — versions `m-v7` (current), `m-v8-rc1` (promoted), `m-v8-rc2`
(rejected); memory-bank hash `7c1d…9ab4`; benchmark set hashes `B1 4f2a…`, `B2 91cc…`,
`B3 0e77…`.

> Anything invented must stay consistent with the above. Dates run **March–August 2026**.
> Currency is BDT with thousands separators. Times are `GMT+6`.

---

## 3. Design principles — the anti-generic rules

This is the section that decides whether the result looks designed or generated. Treat each
line as a constraint, not a suggestion.

**Forbidden outright**
- Purple→blue or teal→cyan gradients on anything. No gradient buttons. No gradient text.
- Glassmorphism, frosted blur panels, neon glows, dark-mode-by-default "crypto" aesthetics.
- Blockchain clichés: chain links, floating cubes, glowing node-and-edge networks, hexagon
  grids, padlock hero icons, isometric servers.
- Emoji as UI iconography.
- Centred hero with a big headline, one-line subhead and two buttons side by side. Every
  generated landing page looks like that.
- Three identical feature cards in a row with an icon on top. If content is genuinely
  parallel, make the cards *unequal* in weight and give one of them the real estate.
- Rounded-everything. Radii above 12px on large surfaces read as toy-like here.
- Drop shadows used for decoration. Shadow means elevation and nothing else.

**Required**
- **Editorial asymmetry.** Use a 12-column grid and deliberately break it: a 7/5 or 8/4
  split, content that starts at column 2, a figure that bleeds into the margin. Symmetry is
  the default of generated layouts; asymmetry with intent is the tell of a designed one.
- **Density where density is honest.** Compliance users read tables. Do not pad a 40-row
  table into airiness — tighten it, give it good rules and alignment, and let it be dense.
  Reserve generous whitespace for the moments that carry meaning (a verification verdict).
- **Optical alignment over metric alignment.** Hang punctuation and quotation marks outside
  the text block. Align a stamp's cap-height to adjacent text, not its bounding box.
- **Tabular numerals everywhere numbers stack.** `font-variant-numeric: tabular-nums`.
- **One accent, used sparingly.** Brass is the only accent. If more than roughly 5% of a
  screen is brass, it has stopped meaning "act here".
- **Type does the work.** Hierarchy comes from size, weight and spacing — not from coloured
  boxes around everything.
- **Real hashes, truncated with intent.** Show first 12 and last 4 characters with a middle
  ellipsis, in mono, with a click-to-copy affordance. Never fake a hash with `xxxx`.
- **Borders over shadows** for separating content on the loom background. A `1px`
  `color/thread` at 40% is the workhorse divider.

**The five-second test.** On the Verification Result screen, someone who does not know what
a hash is must be able to answer "is this genuine?" in five seconds. If any technical
element competes with the verdict for attention, the screen has failed.

---

## 4. Tokens

### 4.1 Colour

Single mode. This product does not need dark mode; do not build one.

| Token | Hex | Use |
|---|---|---|
| `color/ink` | `#141A22` | primary text |
| `color/ink-70` | `#141A22` @ 70% | secondary text |
| `color/ink-45` | `#141A22` @ 45% | tertiary text, captions |
| `color/indigo-900` | `#1E2A44` | sidebar, hero surfaces, gate panels |
| `color/indigo-700` | `#26355380` | sidebar hover |
| `color/indigo-600` | `#33456B` | buttons, links |
| `color/loom-100` | `#EDEAE0` | page background |
| `color/loom-50` | `#F7F5EF` | card background |
| `color/white` | `#FFFFFF` | elevated surfaces, table bodies |
| `color/brass` | `#B08A3E` | accent, active nav, focus, primary action |
| `color/brass-12` | `#B08A3E` @ 12% | accent fill, selected row |
| `color/verified` | `#2E6B5E` | verified · committed · promoted · measured |
| `color/verified-12` | `#2E6B5E` @ 12% | success surface |
| `color/rust` | `#9C4A34` | rejected · revoked · failed · specified |
| `color/rust-12` | `#9C4A34` @ 12% | error surface |
| `color/thread` | `#9B9384` | dividers, inactive, superseded, expired |

**Semantic mapping — apply exactly.**

| Meaning | Token | Appears as |
|---|---|---|
| Committed · Verified · Promoted · Active grant | `verified` | filled dot + label |
| Pending review · Awaiting endorsement · Expiring soon | `brass` | filled dot + label |
| Revoked · Failed · Rejected · Suspended | `rust` | filled dot + label |
| Superseded · Expired · Inactive · Read-only | `thread` | hollow dot + label |

Contrast: `verified`, `rust` and `indigo-600` all pass AA on `loom-50` and white. `brass` on
white is **AA for large text only** — never use brass for body copy; use it for fills,
rules, icons and 18px+ semibold labels. Brass text on `indigo-900` passes.

### 4.2 Type

| Style | Font | Size / weight / leading | Use |
|---|---|---|---|
| `display/hero` | Fraunces | 64 / 600 / 1.05, optical size 96 | landing hero only |
| `display/h1` | Fraunces | 44 / 600 / 1.12 | page titles |
| `display/h2` | Fraunces | 26 / 600 / 1.2 | section headings |
| `display/h3` | Fraunces | 20 / 600 / 1.3 | card headings |
| `body/lead` | Inter | 17 / 400 / 1.65 | intros, verdict explanations |
| `body/base` | Inter | 15 / 400 / 1.55 | general copy |
| `body/small` | Inter | 13 / 400 / 1.5 | captions, helper text |
| `ui/label` | Inter | 13 / 500 / 1.2 | form labels, buttons |
| `mono/label` | IBM Plex Mono | 12 / 500, +6% tracking, uppercase | eyebrows, stamps, table headers, step pills |
| `mono/data` | IBM Plex Mono | 13 / 400 | hashes, MSP IDs, purpose codes, IDs |
| `mono/figure` | IBM Plex Mono | 32 / 500, tabular | KPI numbers |

Fraunces: use `wght 600`, `SOFT 0`, `WONK 0`, optical size matched to point size. Never
Fraunces below 20px. Fallbacks: `Fraunces, "Iowan Old Style", Georgia, serif` ·
`Inter, -apple-system, "Segoe UI", sans-serif` · `"IBM Plex Mono", "SF Mono", Menlo, monospace`.

### 4.3 Spacing, radius, elevation, grid

- Spacing scale (bind to auto-layout, never hand-type): `xs 4 · sm 8 · md 16 · lg 24 · xl 40 · 2xl 64 · 3xl 96`.
- Radius: `sm 4` (stamps, pills, inputs) · `md 8` (cards, buttons) · `lg 12` (modals, hero
  panels). Nothing larger. Full-round only for avatars and status dots.
- Elevation: `e0` flat with a `1px thread@40%` border · `e1` `0 1px 2px ink@6%` for cards ·
  `e2` `0 8px 24px ink@10%` for popovers and dropdowns · `e3` `0 16px 48px ink@16%` for
  modals. Nothing else.
- Grid: 12 columns, 24px gutter, 1240px max content width, 32px page padding. App shell:
  sidebar 248px fixed, content fluid.
- Border: default `1px solid color/thread @ 40%`. Emphasis `1px solid ink @ 12%`.

### 4.4 Motion

| Token | Duration | Curve | Use |
|---|---|---|---|
| `motion/instant` | 90ms | `ease-out` | hover, focus |
| `motion/fast` | 160ms | `cubic-bezier(.2,0,0,1)` | toggles, accordions, tabs |
| `motion/base` | 260ms | `cubic-bezier(.2,0,0,1)` | modals, drawers, step advance |
| `motion/slow` | 420ms | `cubic-bezier(.16,1,.3,1)` | verdict reveal, hero elements |
| `motion/scrub` | — | linear, tied to scroll | parallax and pinned sequences |

Motion rules: nothing moves more than 24px unless it is a parallax layer. Never animate
`width`/`height`/`top`/`left` — only `transform` and `opacity`. Stagger sibling reveals by
40ms, never more. **Every scroll effect must have a `prefers-reduced-motion` fallback that
shows the final state immediately** — specified per section in §9.

---

## 5. Signature components

Build these first; they carry the identity.

### 5.1 `StatusStamp` — the epistemic label
Variant axis `state`: `measured | simulated | specified | assumption`.
Rectangular, `radius/sm`, `1px` border, transparent fill, `mono/label` text, `4px 8px`
padding. Colour by state: measured → `verified` · simulated → `indigo-600` · specified →
`rust` · assumption → `thread`. Border and text share the colour; no fill.
Used on: every metric, every claim on the landing page, model cards, gate decisions, SLA
figures, and the limitations list. **A number without a stamp is a bug.**

### 5.2 `StatusPill` — the operational state
Variant axis `state`: `committed | verified | pending | revoked | failed | superseded |
expired | active`. Pill (`radius/full`), 12% tint fill of its semantic colour, same-colour
text, 6px dot on the left, `ui/label` at 12px. Distinct from `StatusStamp` — pills describe
*what happened*, stamps describe *how well we know it*.

### 5.3 `HashChip`
`mono/data`, `loom-100` fill, `radius/sm`, `2px 6px`. Renders `a3f9e2c817b4…0d3f` (first 12,
ellipsis, last 4). Click copies the full value and swaps to a `Copied` state for 1.2s.
Hover reveals the full value in a tooltip. Never wraps.

### 5.4 `LedgerRow`
Two columns: 200px fixed label (`mono/label`, `ink-45`), flexible body. Optional
instance-swap slot for a `StatusStamp` on the right. Bottom border `thread@40%`. This is the
key/value primitive for every detail panel in the app.

### 5.5 `ProofPath`
The Merkle verification display. Two side-by-side blocks labelled **Computed root** and
**On-chain root**, each a wrapped `mono/data` hash, with a centred `MATCH` or `NO MATCH`
badge between them (`verified` / `rust`). Below, a collapsed **Show steps** disclosure
revealing the sibling-hash ladder as an indented list of 7 steps, each with its index, the
sibling hash and whether it was applied left or right.

### 5.6 `FlowStep` and `Stepper`
Horizontal row of numbered steps. Variant axis `state`: `pending | active | done`. Pending →
`thread` hollow circle · active → `brass` filled with a 2px ring · done → `verified` filled
with a check. The connector rule between steps fills with `verified` as it completes.
Used by upload commit (5 steps) and the Continuity Gate (7 steps).

### 5.7 Other components to build
`Button` (`primary` indigo-600 fill / `secondary` outline / `ghost` / `danger` rust; sizes
`sm 32` `md 40` `lg 48`; states default/hover/active/focus/disabled/loading) ·
`Input` `Select` `DatePicker` `MonthPicker` `Textarea` `FileDrop` `Checkbox` `Radio`
`ToggleSwitch` (label, helper, error states each) · `Tabs` · `Table` (sortable header,
zebra off, row hover `brass-12`, sticky header, empty state) · `Card` · `Modal` ·
`Drawer` · `Toast` · `Tooltip` · `Breadcrumb` · `Pagination` · `SearchField` ·
`Avatar` · `OrgBadge` (org name + MSP chip) · `EndorsementBar` (n of m + segment fill) ·
`KpiCard` (label, `mono/figure` value, delta, target line, optional `StatusStamp`) ·
`Timeline` · `EmptyState` · `Skeleton` · `CodeBlock`.

---

## 6. Navigation and routes

App shell: fixed `indigo-900` sidebar (248px) — wordmark, role-scoped nav, user block and
sign-out pinned to the bottom. Content area `loom-100`. Every page has a header row: title
in `display/h1`, role chip, and an organisation switcher on the right.

Active nav item: `brass-12` fill, 2px brass left rule, brass icon and label.

| Role | Routes |
|---|---|
| Factory staff | `/factory/dashboard` · `/factory/upload` · `/factory/records` · `/factory/records/:id` · `/factory/access` · `/factory/model` |
| Buyer | `/buyer/portal` · `/buyer/verify/:id` · `/buyer/suppliers` |
| Auditor | `/auditor/workspace` · `/auditor/portal` · `/auditor/verify/:id` · `/auditor/attestations` |
| Consortium admin | `/governance` · `/governance/members` · `/governance/enrol` · `/ops/sla` · `/ops/incidents/:id` · `/model/registry` · `/model/rounds` · `/model/gate/:id` · `/model/benchmarks` · `/model/memory-bank` · `/ledger` · `/ledger/block/:n` |
| Regulator | `/regulator` · `/regulator/sla` · `/ledger` (read-only) |
| Public | `/` (landing) · `/verify` · `/verify/receipt/:id` · `/docs` |
| Any | `/settings` · `/settings/keys` · `/notifications` · `/search` · `/403` · `/404` · `/500` |

---

## 7. Screens that already exist — re-specify these

These eleven were built in Figma Make. Keep the information architecture; re-skin to §4 and
add the states listed. Every control below is required.

### 7.1 Login `/login`
Centred card on `indigo-900`, wordmark above. Title "Sign in", subtitle "Select your role to
continue. This demo uses simulated authentication."
- Five role cards in a vertical stack, each: icon, role name (`display/h3`), organisation
  (`body/small`, `ink-45`), one-line capability description, and a right-aligned radio.
  Selected → 2px `brass` border + `brass-12` fill. Hover → border `ink@12%`.
- `Continue →` primary button, full width, disabled until a role is selected.
- **Step 2, two-step verification:** 6-digit code input (single field, `mono/data`, 24px,
  centred, letter-spaced), `Sign in →`, `Back` link, and helper "Demo: any 6-digit code
  works." Error state: "Invalid code. For this demo, enter any 6-digit number." in `rust`.
- Footer: "Breadcrumbs · Team CookieMonsters, United International University · 2026".
- Add: loading state on Sign in; a "Verify a record without signing in →" link to `/verify`.

### 7.2 Factory Dashboard `/factory/dashboard`
- Four `KpiCard`s: Records committed this month (`2`) · Pending requests awaiting your
  response (`1`, brass dot) · Active grants currently open (`2`) · Expiring soon within 30
  days (`1`, warning icon).
- Full-width CTA banner, `verified` fill, white text: "Ready to commit a new record?" /
  "Upload a finalized export — payroll, safety, chemical, or maintenance." + `Upload record`
  button (white fill, `verified` text).
- Two columns. **Recent commitments** (`View all →`): rows of record type, period, row
  count, `StatusPill`. **Access requests** (`Manage all →`): requester org, one-line purpose,
  `StatusPill`.
- **Recent activity** timeline: icon, sentence, right-aligned timestamp — e.g. "Payroll
  register for July 2026 committed to ledger", "Access revoked: BV Certification exceeded
  agreed scope" (rust icon).
- Add: empty state for a factory with zero commitments (illustration-free — a bordered panel,
  one sentence, and the upload CTA).

### 7.3 Upload & Commit `/factory/upload`
- **Record details** card: `Record type` select (5 types) · `Period` month picker ·
  `Schema version` select (`v2.1.0` default, with a "What changed?" link to the schema registry).
- **Select file** card: dashed `FileDrop`, "Drop a CSV or Excel file here / or click to
  browse". States: idle, drag-over (`brass` border, `brass-12` fill), file selected (filename,
  size, row count, `Remove`), invalid type, too large, schema mismatch (list the offending
  columns).
- `Commit record to ledger` primary, disabled until type + period + file are all set.
- **Commit sequence** — replaces the card with a 5-step `Stepper`, ~700ms per step:
  `Normalise → Salt & hash rows → Build Merkle tree → Encrypt & store off-chain → Commit to ledger`.
  Each step shows a one-line plain-language explanation while active.
- **Confirmation**: `verified` panel — commitment ID, Merkle root (`HashChip`), block number,
  timestamp, row count, and three actions: `View record`, `Grant access`, `Commit another`.
- Add: an explicit "What leaves your building" note — "The file itself is encrypted and
  stays on your own storage. Only the root hash and the record type, period and site go to
  the ledger." with a `StatusStamp specified`.

### 7.4 Record Detail `/factory/records/:id`
- Back link. Header: record type (`display/h1`), org · period, `StatusPill`.
- Three `LedgerRow` figures: Rows committed (`1,847`), Schema version (`v2.1.0`), Committed
  (`5 Aug 2026`).
- `Technical details ⌄` disclosure, **collapsed by default**: Merkle root, transaction ID,
  block number, channel, chaincode, endorsing peers, salt policy, encryption key ID.
- **Commitment history** timeline: "Record committed to ledger" (with tx hash), "Verification
  completed — proof matched on-chain root". Footer of the card: `StatusPill committed` +
  `Block #14,821`.
- **Verification receipts** panel: count, then one card per receipt — requester org,
  `StatusPill verified`, date and the field verified (`net_pay_bdt`).
- **Superseded versions**: linked list to prior commitments with a "why superseded" reason.
- `Grant access to a buyer or auditor` panel + `Manage access` primary button.

### 7.5 Access Grant Management `/factory/access`
- Filter tabs with counts: `All 5` `Pending 1` `Active 2` `Expired 1` `Revoked 1`.
- Table: **Requester** (org + MSP chip) · **Record** (type + period) · **Purpose** (code in
  `mono/data` + plain-language name) · **Expiry** (countdown — `30d`, `45d`, `1d` in rust
  when ≤7d, or `Expired`) · **Scope** (the exact field, e.g. `net_pay_bdt`) · **Status** ·
  **Actions**.
- Row actions: `Approve` / `Deny` for pending; `Revoke` for active; `View receipt` for used.
- Confirmation modal on Revoke: names the org, the record and the consequence — "They will
  immediately lose the ability to verify this record. The revocation is written to the ledger
  and cannot be removed." + `Reason` select + `Revoke access` danger button.
- Add: bulk selection with a sticky action bar; sort by expiry; empty state per tab.

### 7.6 Buyer Request Portal `/buyer/portal`
- **New verification request** card, with the constraint stated up front: "You will only
  receive the single fact you request — never the full file."
  Fields: `Supplier factory` select · `Record type` select · `Period` month picker ·
  `Specific item reference` text input (placeholder `e.g. worker_id=APX-4421`, helper "e.g.
  worker ID, inspection date, equipment ID — as narrow as possible") · `Purpose code` select
  (shows the plain-language name beneath) · `Access expiry date` date picker ·
  `+ Submit request` primary.
- **My requests** side panel: cards with supplier, record + period, `StatusPill`, requested
  date. Statuses seen: Committed, Pending Review, Access Expired, Revoked.
- Add: inline validation ("Choose a supplier factory"), a scope-narrowing hint if the item
  reference is left blank, and a success toast with a link to the request.

### 7.7 Verification Result `/verify/:id` — the most important screen
- **Verdict banner**, full width, `verified-12` fill with a `verified` 2px left rule:
  check icon, `display/h1` **"Verified — record is genuine"**, then `body/lead`: "This entry
  matches the factory's committed record from Saturday, 22 August 2026. The value has not
  been changed since it was sealed on the ledger."
  Failure variant: `rust`, **"Proof failed — do not rely on this record"**, and a plain
  explanation of what that means and what to do next.
- **Disclosed fact** card: field name in `mono/label` (`net_pay_bdt`), value in
  `display/h1` (`14,820 BDT`), `StatusPill verified`. Caption: "Only this single value was
  disclosed to verify the record. No other data from the register was transmitted or revealed."
- **How we checked this** disclosure (open by default, but visually quiet): explanatory
  sentence, then the `ProofPath` component with `Show steps`.
- **Verification Receipt** card with `Download (PDF/JSON)`: `LedgerRow`s for Requester,
  Purpose, Verified field, Disclosed value, Verification time, Result, Transaction ID,
  Block, Benchmark/model version used.
- Motion: the verdict banner fades and rises 12px over `motion/slow` on mount; everything
  else is static. Nothing competes with the verdict.

### 7.8 Auditor Batch Workspace `/auditor/workspace`
- Four KPIs: Total items `4` · Passed `2` (verified) · Failed `0` (rust) · Queued `2` (brass).
- **Verification queue** card with `⤓ Add claims CSV` secondary and `Run 2 queued` primary.
  Table: Factory · Record type · Period · Commitment ID (`mono/data`) · Result (`StatusPill`).
  Running state: each row animates through checking → result, ~400ms apart, with a
  progress bar in the card header.
- **Attestation composer**: `Claim code` input (`ISO45001-PASS-2026`) · `Evidence scope`
  select (`All records in this batch` / `Passed records only` / `Selected records`) ·
  `Attestation statement` textarea ("Describe your findings in plain language…") ·
  `✎ Sign & submit attestation` primary, **disabled until every queued item has run**, with
  the reason shown as helper text.
- **Attestation history**: past attestations with claim code, `StatusPill verified`, summary,
  auditor name and date.

### 7.9 Governance Console `/governance`
- Tabs: `Proposals` · `Members`.
- **Proposal cards**, one per proposal: eyebrow with type (`NEW MEMBER` / `POLICY CHANGE` /
  `SUSPENSION`) + `StatusPill`; title (`display/h3`); body paragraph; `EndorsementBar`
  ("2 of 3 endorsements required") with a `⏱ 26d remaining` counter; endorser chips
  (`✓ ApexTextile`, `✓ NoorGarments`); actions `✓ Endorse` primary and `Request more info`
  secondary. When threshold is met, actions are replaced by a `verified` banner: "Threshold
  reached — proposal approved".
- **Members tab**: Active member directory table — Organisation · MSP ID (`mono/data`) ·
  Role · Country · Joined · Status · row action `View`.
- Add: `+ New proposal` button and its modal (type select, title, description, endorsement
  threshold, deadline); a proposal detail drawer showing the full endorsement ledger trail.

### 7.10 SLA & Operations `/ops/sla`
- Four KPIs with target lines and `StatusStamp`s: Monthly uptime `99.933%` (target ≥99.5%) ·
  Total verifications `1,663` (August 2026) · Avg. response time `170 ms` (target <500ms) ·
  RPO/RTO `15 min / 4 hr`.
- **Portal uptime — August 2026**: line chart, y-axis 97–100.1%, daily x-axis, target line
  at 99.5% dashed in `thread`, the dip on 08-11 annotated and clickable through to the
  incident.
- **Daily verifications**: bar chart, brass bars.
- **Certificate revocation log** with `⤓ Export`: currently the empty state — "No
  certificate revocations in the last 30 days." + "Target: revocation actioned within 1 hour
  of confirmed compromise."
- Add: date-range selector, an incident log table (severity, opened, resolved, duration,
  cause), and per-organisation peer health.

### 7.11 Regulator Observer `/regulator`
- **Read-only banner**, `indigo-900` fill, white text, eye icon: "Read-only observer access —
  You are viewing aggregate governance statistics and events only. Factory-level records and
  personal data require a separate lawful-basis access grant."
- Four KPIs: Active factories `2` · Total organisations `7` · Open proposals `2` · Schema
  versions in use `4`.
- **Governance event log** with the caption "Aggregate events only — no factory data":
  `StatusPill` + sentence + date + org.
- **Organisation participation** panel.
- Every control that would reveal factory data must be *visibly present and disabled*, with
  a tooltip explaining the lawful-basis requirement. That absence is the point of the screen.

---

## 8. Screens that are missing — build these

The existing build covers document custody and part of governance. It has **no screens at
all** for the learning plane or the Continuity Gate — the paper's main contribution — and no
ledger explorer, in a blockchain product. These are the gap.

### 8.1 `/model/gate/:id` — Continuity Gate Decision ★ the demo's money shot
The single most important new screen. It must make a contract decision legible to a
non-technical judge in under fifteen seconds.

- **Decision banner**: for a rejection, `rust-12` fill, `rust` left rule, `display/h1`
  **"Candidate rejected — it forgot an earlier task"**, then: "Model `m-v8-rc2` improved on
  chemical-inventory misreporting but lost 11.4 points on wage-register inconsistency, which
  the network already knew. The previous model `m-v7` remains in force." Promote variant is
  `verified`: **"Candidate promoted — nothing was forgotten"**.
- **Per-task benchmark table** — the heart of it. Rows = tasks (Wage-register inconsistency,
  Forged compliance certificate, Chemical-inventory misreporting). Columns: Benchmark
  (hash chip) · Committed before round (timestamp) · Previous model accuracy · Candidate
  accuracy · Change (signed, coloured, with a small bar) · Tolerance τ · Verdict per row
  (`Pass` / `Fail`). The failing row gets a `rust` tint and a left rule.
- **Rule strip**: the three gate parameters as `LedgerRow`s — minimum gain on the new task
  `γ = +2.0pp`, maximum loss on any earlier task `τ = 3.0pp`, required endorsements `k = 3
  of 5`, agreement tolerance `δ = 1.0pp`.
- **Endorser panel**: one row per endorsing organisation — org, MSP, the accuracies it
  signed, its signature (`HashChip`), and whether it agreed within δ. Show the **median**
  used by the contract, explicitly.
- **7-step `Stepper`** replaying what the contract did: `Verify benchmark hashes → Collect
  signed submissions → Check endorsement threshold → Check agreement within δ → Take medians
  → Test gain on new task → Test regression on earlier tasks`. Include a `▷ Replay decision`
  button that animates it at ~260ms per step (this is the live demo control).
- **Ledger record**: transaction ID, block, model hash, parent model hash, memory-bank hash,
  contributor list, endorser set, and a `Verify this decision yourself` button that
  recomputes from ledger data.
- `StatusStamp specified` until the gate has actually run in the build; `measured` after.

### 8.2 `/model/registry` — Model Registry & Lineage
Version cards in a vertical lineage with connector rules: version ID, `StatusPill`
(promoted / rejected / superseded / in force), created date, parent version, memory-bank
hash, contributor count, and per-task accuracy sparklines. Rejected versions stay visible
with the rejection reason — the audit trail is the feature. Filters by status and date.
Detail drawer per version. A prominent `In force` marker on the current model.

### 8.3 `/model/rounds` — Federated Round Monitor
- KPIs: current round, participating factories, records trained on this round (aggregate
  only), round duration.
- **Round timeline**: `Local training → Clipping & noise → Robust aggregation (trimmed mean)
  → Candidate assembled → Gate evaluation`. Live state per stage.
- **Participant table**: factory, MSP, updates submitted, contribution score, weight in
  aggregation, status, and whether it was trimmed as an outlier (with a `Trimmed` pill).
- **Privacy panel**, stated honestly: clipping norm, noise σ, what is shared and what is
  not, and a `StatusStamp specified` on the components not yet implemented. Include the
  report's own caveat: the added noise is *not* differential privacy — no sensitivity bound,
  no budget, and released variances and counts are unnoised.

### 8.4 `/model/benchmarks` — Benchmark Commitment & Reveal
Explains the anti-gaming design. Table: task, benchmark hash committed, committed at,
contributed by (rotating subset of members), revealed (yes/no + when), size. Two states per
row: **sealed** (hash only, lock icon, `thread`) and **revealed** (hash + contents link,
after promotion is decided). A short explainer panel: why the set is hashed before the round
and revealed only after, and the honest limitation — this converts quiet cheating into
something requiring collusion; it does not eliminate it.

### 8.5 `/model/memory-bank` — Memory Bank Inspector
Per category: number of cluster centres, spread, count, the noise σ applied, and the bank
hash anchored on-chain. A small 2-D projection plot of prototype centres (no raw records —
say so on the screen). Version history of bank hashes with the model versions each was bound
to. `StatusStamp simulated` on the visualisation.

### 8.6 `/ledger` and `/ledger/block/:n` — Ledger Explorer
A blockchain product needs this. Block list: height, timestamp, transaction count, channel,
proposer, block hash. Block detail: header (previous hash, data hash, block hash), and per
transaction — tx ID, chaincode invoked, submitter MSP, endorsers, read-set/write-set,
validation code. Filters by channel (`documents-apex-primark`, `model-channel`) and by
chaincode (`doccustody`, `fedmodel`, `reputation`). A `Verify chain integrity` action that
walks the hash links and reports. Search by tx ID, block or hash.

### 8.7 `/verify` — Public Verification (no login)
The screen a buyer's compliance officer uses without an account. Single centred input:
"Paste a receipt ID, verification link, or scan a QR code". `Verify` primary. Result routes
to §7.7's layout in a public shell (no sidebar). Nothing about the factory beyond the
disclosed fact is shown. This is the screen most likely to be demoed on a phone — design it
mobile-first.

### 8.8 `/governance/enrol` — Member Enrolment Wizard
Four steps: **Organisation details** (legal name, country, role, registration number) →
**Identity** (MSP ID, CSR upload or generate keypair, certificate preview) → **Channels**
(which channels this member joins) → **Review & submit for endorsement**. Step rail on the
left, one card per step, `Back`/`Continue`, and a final summary that becomes a governance
proposal. Show the issued certificate's subject, issuer, validity and fingerprint.

### 8.9 `/settings` and `/settings/keys`
Profile (name, email, org, role — org and role read-only). Notification preferences per
event type. Session list with revoke. **Key management**: signing key fingerprint, issued
by, expires, `Rotate key` (with a confirmation modal explaining ledger consequences),
`Download public certificate`, and a revocation-status indicator.

### 8.10 `/notifications`
Grouped by day. Types: access request received, grant expiring, model promoted, **model
rejected**, proposal needs your endorsement, incident opened, certificate expiring. Each has
an icon, sentence, org, timestamp, read/unread state and a deep link. `Mark all read`,
filter by type.

### 8.11 `/search`
Global search across records, commitments, transactions, organisations and proposals.
Results grouped by type with a keyboard-navigable list. Trigger with `⌘K` from anywhere.

### 8.12 `/ops/incidents/:id`
Incident detail from the SLA dip: severity, opened/resolved, duration, affected components,
root cause, remediation, and the linked ledger events during the window.

### 8.13 Schema Registry `/settings/schemas`
Versions `v2.1.0`, `v2.0.3`, `v1.9.0`, `v1.8.2` with per-version field lists, required/
optional flags, validation rules, a diff view between versions, and which committed records
use each. Reached from the "What changed?" link in §7.3.

### 8.14 Error and edge screens
`/403` **Scope denied** — "Your grant covers `net_pay_bdt` for July 2026. It does not cover
this field." with the exact grant shown and a `Request wider scope` action. `/404`. `/500`.
Session-expired modal. Offline banner. Ledger-unreachable state (the app must degrade
honestly: "The ledger is not reachable. Verification is unavailable; nothing has been lost.").

---

## 9. Landing page `/` — parallax and scroll choreography

Public marketing and explainer page. This is where the interactive widgets from
`breadcrumbs-figma-system.md` live. It must feel like a piece of publishing, not a SaaS
template.

**Global scroll behaviour.** Use a scroll-linked system (Framer Motion `useScroll` +
`useTransform`, or GSAP ScrollTrigger). Parallax layers move on `transform: translate3d`
only. Target 60fps; never attach anything expensive to the scroll handler. **Every section
below lists its reduced-motion fallback, and all of them are "render the final state, no
movement".**

### §1 Hero — "The record, the fingerprint, the block"
Full-viewport, `indigo-900`. Four depth layers, each moving at a different rate as you
scroll the first 100vh:

| Layer | Content | Parallax rate |
|---|---|---|
| L0 back | Very large, low-contrast Fraunces numeral or woven-texture field | `0.15×` |
| L1 | A payroll register page rendered as fine ruled lines and blurred type | `0.35×` |
| L2 | The Merkle tree drawn as thin brass rules, forming upward | `0.6×` |
| L3 front | Headline, subhead, actions | `1.0×` (static) |

Headline in `display/hero`: **"Prove one line. Reveal nothing else."** Subhead in
`body/lead`, `loom-100` at 80%: "Breadcrumbs is a permissioned ledger that makes a factory's
own records provable — without publishing them, and without trusting whoever runs the
server." Actions: `See a verification` (primary brass) and `Read the paper` (ghost, white
outline). Below them, a small `StatusStamp specified` with "Prototype — Blockchain Olympiad
2026 finals" — honesty as a design feature, right in the hero.

On load: L1 and L2 fade in and settle upward 16px over `motion/slow`, staggered 40ms.
Scroll cue at the bottom, a 1px brass rule that grows and shrinks.
*Reduced motion: all layers static at final position, no fade.*

### §2 The problem — pinned type sequence
Pin the section for ~200vh. Three sentences replace one another as scroll progresses, each
cross-fading and rising 12px:
1. "A factory's records are its own word for what happened."
2. "A buyer has no way to check them without taking the whole file."
3. "So audits copy everything, and prove almost nothing."
A thin progress rule on the left tracks position through the three.
*Reduced motion: the three sentences render as a normal stacked list, no pin.*

### §3 Why a blockchain — the Decision Toggle widget
Interactive, not scroll-driven. Three `ToggleSwitch`es, all on by default:
`Multiple parties write to the same record` · `No single trusted custodian` ·
`The parties do not fully trust each other`.
Below, `VerdictBanner` with two variants driven by an expression:
all three on → **"A blockchain is justified"** (`verified`); any off → **"Use a database"**
(`thread`). Copy beneath explains that this is the Wüst–Gervais test, and that Breadcrumbs
only claims the first verdict because all three hold in this industry.
This is the strongest possible answer to "why not just a database" — the visitor proves it
to themselves. *Reduced motion: unaffected; it is click-driven.*

### §4 The three planes — horizontal scroll-pinned
Pin for ~250vh; the three plane panels translate horizontally as you scroll vertically.
Plane A *Record custody* → Plane C *Governance* → Plane B *Learning*. Each panel: eyebrow in
`mono/label`, `display/h2` title, a short paragraph, and a `PlaneAccordion` listing its
steps. The plane bands use the report's own colour coding.
*Reduced motion: the three panels stack vertically, accordions closed, no pin or translate.*

### §5 Selective disclosure — the Merkle Stepper
The centrepiece explainer. A wage register of 8 visible rows; one row is highlighted. Press
`Next step` seven times and watch: hash the row → hash its sibling → combine → climb → climb
→ climb → reach the root → compare to the ledger. Each step draws one brass rule and writes
one hash. The other seven rows visibly stay redacted throughout.
Punchline, revealed only at step 7: **"The buyer learned one number. The other 1,846 rows
never left the building."**
Include `Reset`. Button becomes non-interactive at step 7.
*Reduced motion: unaffected; it is click-driven. Do not autoplay it.*

### §6 The Continuity Gate — the Gate Simulator
Two buttons: `Submit good candidate` and `Submit forgetful candidate`. Either starts a
7-step `FlowStep` chain at 260ms intervals, ending in a `promote` (`verified`) or `reject`
(`rust`) outcome panel. The reject outcome shows the per-task table in miniature with the
failing row highlighted, and the line: **"The contract refused it. No single participant,
including whoever runs the server, could overrule that."**
Add a `StatusStamp specified`/`measured` bound to whether the real gate is running yet.
*Reduced motion: skip the delay chain — jump straight to the outcome panel.*

### §7 Where we sit — comparison
The market table from the report, rendered as a matrix with the last column ("Gate on past
tasks") emphasised as the only one Breadcrumbs fills. Rows fade in on enter, staggered 40ms.
Explicitly name what Breadcrumbs does *not* beat — notarisation services, LiFeChain,
Digital Product Passports. Losing columns visibly is more persuasive than winning all of them.
*Reduced motion: no stagger, table renders complete.*

### §8 Honest limitations — `LimitationRow` list
Nine numbered rows straight from §12 of the report, each with a `StatusStamp`. Heading:
**"What we cannot do yet."** No animation beyond a fade on enter. This section is the whole
brand argument: nobody else in the competition will publish their own weaknesses on their
landing page.

### §9 Close
`indigo-900`. Restate the one line. Two actions: `Verify a record` → `/verify`,
`Sign in` → `/login`. Footer: team, institution, year, repository link, and the report PDF.

---

## 10. Cross-cutting states

Every screen needs all five. Do not ship a screen with only its happy path.

- **Loading** — `Skeleton` blocks matching final layout geometry. Never a centred spinner on
  a full page. Tables get 5 skeleton rows; KPIs get skeleton figures.
- **Empty** — bordered panel, one `display/h3` line, one `body/base` sentence of guidance,
  and the single most useful action. No illustrations, no mascots.
- **Error** — inline where the error is local; a `rust` banner where it is page-level. Always
  say what happened, what it means, and what to do. Never "Something went wrong".
- **Permission denied** — show the control, disabled, with a tooltip naming the missing
  grant or role. Hiding it teaches the user nothing.
- **Stale/offline** — a persistent banner: "Showing data from 14:02. The ledger is not
  reachable." Verification actions disable; reads continue.

---

## 11. Responsive

Breakpoints: `sm 640` · `md 768` · `lg 1024` · `xl 1280` · `2xl 1536`.

- **≥1024** full shell, sidebar visible.
- **768–1023** sidebar collapses to a 64px icon rail with tooltips; KPI grids go 4→2.
- **<768** sidebar becomes a bottom sheet from a header menu button; KPI grids go to 1
  column; **tables become stacked cards**, one card per row with the columns as
  `LedgerRow`s — never a horizontally scrolling table on mobile.
- `/verify` and `/verify/receipt/:id` are **designed mobile-first** — they will be demoed on
  a phone. The verdict banner and disclosed fact must fit in one viewport at 375px.
- Landing page: all pinned/horizontal sections degrade to vertical stacks below `1024`.

---

## 12. Accessibility

- AA minimum for all text; AAA for the verdict banner copy.
- Brass is never body-copy text (see §4.1).
- Visible focus on every interactive element: 2px `brass` ring, 2px offset. Never remove it.
- Full keyboard paths for: role selection and sign-in, upload and commit, grant/revoke
  (including modal focus trapping and restore), request submission, batch run, endorsement,
  and gate replay.
- Status is never carried by colour alone — always a dot shape, icon or word alongside.
- Charts have a data-table equivalent behind a `View as table` toggle.
- Hashes are `aria-label`led with their full value; the truncation is visual only.
- Live regions announce commit-step progress, batch results and gate outcomes.
- `prefers-reduced-motion` honoured per §9.

---

## 13. Microcopy rules

- Plain language first, technical term in a parenthetical or a disclosure — never the reverse.
  "Fingerprint (Merkle root)", not "Merkle root (fingerprint)".
- Never claim more than is true. Use "committed", "matched", "attested" — not "guaranteed",
  "immutable", "100% secure", "trustless".
- Buttons are verbs with objects: `Commit record to ledger`, `Sign & submit attestation`,
  `Revoke access`. Never `Submit`, `OK`, `Confirm` alone.
- Destructive confirmations state the permanent consequence in one sentence.
- Dates: `5 Aug 2026`. Times: `17:04 GMT+6`. Numbers: thousands separators, tabular figures.
- The word "blockchain" appears rarely in the product UI — users care about "committed",
  "verified" and "who can see this". Save it for the landing page and the explorer.

---

## 14. Build order

1. Tokens, then §5 signature components, then the shared shell.
2. `/verify/:id` — it is the product's thesis in one screen.
3. `/model/gate/:id` — the demo's climax.
4. The factory flow: dashboard → upload → record detail → access.
5. Buyer, auditor, governance, SLA, regulator.
6. Ledger explorer, model registry, rounds, benchmarks, memory bank.
7. Landing page.
8. Settings, notifications, search, error states.

## 15. Hand back

React + TypeScript, `react-router-dom`, `recharts`, `lucide-react` — matching the scaffold in
this directory. Tokens as CSS custom properties. One component per file. No inline hex
values anywhere; every colour resolves to a token.
