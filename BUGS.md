# Bugs found during the 2026-09-03 walkthrough

Found by driving the running app as each of the five roles, and by reading the
API against the screens that call it. Every one below is reachable by a judge
clicking around at the finals.

Bugs 1–4 were fixed in the first pass. Bug 5 was left open. Bugs 5–15 are the
second pass: the request→grant→verify path a judge is most likely to walk, and
the factory's side of it, which had almost no controls at all.

**Status: all fifteen fixed.** Verified live against the running app; 251 tests
pass, `tsc --noEmit` is clean and the production build is clean.

---

## 1. Detector paragraph collapses into a one-word-per-line column — FIXED

**Where:** `Breadcrumbs Project/frontend/src/components/mechanisms.css:594`
(`.screen__blind`), rendered by `components/Screening.tsx:113`.

**Seen on:** a record detail page — `/factory/records/:id` — after pressing
*Score this record*, in the "What the detector thinks" panel. Reproduced on
`doc-ui-2027-03-mach` (Apex Textile, Machine Maintenance, March 2027).

**Symptom:** the sentence beginning *"It is at chance on cross_inconsistency —
8.3% detection…"* renders as a ~90px vertical sliver, one word per line, and
spills past the panel. Measured: paragraph width 296px, height **507px**,
`scrollWidth` 304 > `clientWidth` 296.

**Cause:** `.screen__blind` is `display: flex` so the `<TriangleAlert>` icon
sits beside the text. But the paragraph's remaining content is a run of loose
text nodes and inline `<span className="mono">` elements, and each becomes its
own flex item on a `flex-wrap: nowrap` line. In the narrow right-hand column of
`.rec__body` (grid `342px 320px`) they are squeezed to nothing. It only looks
correct in a wide container.

**Fix:** make the paragraph exactly two flex items — the icon and one wrapper
element holding all the prose — and stop the icon shrinking:

```css
.screen__blind > svg { flex: none; }
```

with the sentence wrapped in a single `<span>` in `Screening.tsx`. Do not
simply drop `display: flex`; the icon alignment is deliberate.

---

## 2. `production_output` is offered in the UI but rejected by the chaincode — FIXED

**Where:** the record-type `<select>` on `/factory/upload`
(`frontend/src/pages/Upload.tsx`) versus `VALID_TYPES` in
`Breadcrumbs Project/model/chaincode/doccustody.py:43`.

**Symptom:** choosing *Production Output*, attaching a CSV and pressing
*Seal to the ledger* fails with:

```
unknown record type production_output
CHAINCODE_REJECTED
```

**Cause:** the dropdown offers six record types; the chaincode's `VALID_TYPES`
knows five — `payroll_register`, `safety_inspection`, `chemical_inventory`,
`machine_maintenance`, `compliance_certificate`. `production_output` is in
neither `VALID_TYPES` nor `backend/app/corpus.py`.

**Decide which way it goes.** Either add `production_output` to the chaincode
and to the corpus/schema plumbing that a sealed record needs, or remove it from
the dropdown. Removing is the smaller, safer change before the finals; the
error the user currently gets is a raw contract rejection with no guidance.

Whichever way, the two lists should come from one source rather than being
maintained in parallel.

---

## 3. `/verify` sends a signed-in user back to the marketing page — FIXED

**Where:** `Breadcrumbs Project/frontend/src/pages/VerifyResult.tsx`.

**Symptom:** the back link in the header read "← Breadcrumbs" and pointed at `/`
whoever was looking at it. A buyer who had just run a proof and wanted to return
to their portal was dropped on the landing page that explains the product to
strangers, and had to navigate back in from scratch. The footer had the same
problem twice over: "What Breadcrumbs is" and "Sign in to the portal", both
offered to somebody already signed in.

**Fix:** a `useWayBack()` hook returns the signed-in role's own `landing` path
and its instrument name ("The Lightbox", "The Loom Floor", …), falling back to
`/` and "Breadcrumbs" for a visitor holding only a receipt. Both headers use it,
and the footer shows a single "Back to <instrument>" button when signed in.

**Verified live** as James Holloway: header and footer both resolve to
`/buyer/portal`, and the back link reads "← The Lightbox".

---

## 4. A buyer's grant rows never named the document — FIXED

**Where:** `Breadcrumbs Project/frontend/src/pages/Lightbox.tsx` (the buyer's side
panel), `pages/lightbox.css`.

**Symptom.** In "Grants you hold" each row printed the field name and then
`PURPOSE · until <date>` and nothing else. Directly above, "Your requests"
printed `field · Record Type · Period · PURPOSE`. So an active grant for
`cas_number` sat beside a pending request for `cas_number` looking like the same
object in two states — which reads as though the factory's consent had been
skipped and the grant issued automatically.

It had not been. Checked live: all three pending requests carry `grant_id: null`,
and `POST /api/requests` writes a `pending` row and creates no grant. The 259
active grants the buyer holds are seed data — they fall on exactly three dates
(2026-08-05 ×57, 2026-11-05 ×108, 2027-03-05 ×94) at one single time of day,
which is a bulk seeder rather than 259 decisions.

**Why it mattered anyway.** The page's own copy promises the missing detail
twice — *"A request names a period; the grant that answers it names a document"*
and *"A grant covers one field of one record for a fixed window"* — and then the
row omitted the document. A judge reading that screen reaches the same wrong
conclusion a user did.

**Fix:** resolve each grant's `record_id` against the records the page already
fetches, and render `Record Type · Period · PURPOSE · until <date>` with the
document id beneath it in a quieter style. No new API call.

**Verified live** as James Holloway — the row now reads:
`cas_number · Chemical Inventory · July 2026 · REACH-COMPLIANCE · until 31 Dec 2028 · doc-gaz-w2-010295`

---

## 5. No way to re-seal a reopened period — FIXED

**Where:** `Breadcrumbs Project/frontend/src/components/SealActions.tsx`.

`api.amendSeal()` was defined in `lib/api.ts` and **nothing called it**. The
open-periods list was built as:

```js
const sealed = new Set(seals.map((s) => s.bucket));  // includes reopened buckets
if (sealed.has(record.bucket)) continue;             // so they never appear
```

A reopened bucket counted as sealed for that filter, so it was never offered a
"Close this period" button — and there was no amend control anywhere. The
component rendered a banner saying *"N periods are reopened and not yet
re-sealed"* and gave the user no way to act on it. The chaincode's own docstring
names this exact failure: *"the error message described a door that was not
there."*

**Checked at the contract first.** `reopen → commit → amend` works end to end
over the API, so only the control was missing:

```
POST /api/seals/ApexTextileMSP|Narayanganj|chemical_inventory|2026-05/reopen  → reopened, reopening_count 1
POST /api/records            doc-late-nar-001                                → committed, block 1059
POST /api/seals/…/amend      added_record_ids=[doc-late-nar-001]             → version 2, count 6, 1 amendment
```

**One thing the contract will not do, which the UI has to say out loud.**
`amend_seal` requires at least one added record and recomputes the count and
root over everything the ledger holds for the bucket. So a period reopened *by
mistake* cannot simply be closed again: naming a record that was already inside
it would put a false "added" claim on the chain. The honest state is that a
reopened period stays open until the late record it was reopened for actually
exists.

**Fix:** a "Reopened, waiting to be re-sealed" section in `SealActions` listing
each reopened bucket with the reason and date it was reopened, the count it held
then, and what the ledger holds now. Records committed since the reopening are
offered as tick boxes, pre-ticked, with an "Amend and re-seal" button and a
reason field shaped like the existing reopen form. When nothing has been
committed since, the section says why it cannot be re-sealed yet and links
straight to *Seal a record* with the type, period and site already filled in.

---

## 6. A grant the buyer has just been given is invisible to the buyer — FIXED

**Where:** `pages/Lightbox.tsx` (`grants.slice(0, 8)`) and
`pages/VerifyResult.tsx` (`live.slice(0, 60)`).

**Symptom.** The end-to-end demo — buyer asks, factory grants, buyer verifies —
dead-ends at the last step. The new grant appears on no screen the buyer has.

**Cause.** Both lists truncate an *unsorted* array. `list_grants` returns the
chaincode's key order, so the buyer's 259 seeded grants come back as `g-0003`,
`g-0004`, … `g-0313`, and a grant answering request `br-002` is `g-br-002`,
which sorts last. Measured live after granting one:

```
buyer grants: 260   new grant present in first 8? False   position: 259
```

So the portal showed eight grants from 5 Aug 2026 and the `/verify` dropdown
showed sixty of them, and the one just issued was in neither.

**Fix:** sort by `granted_at` descending before truncating, on both screens, and
say what is being shown. The `/verify` dropdown now lists live grants
newest-first with the record type and period beside the id, and the whole list
rather than the first sixty.

---

## 7. `GET /api/records/{id}` was not scoped — FIXED

**Where:** `backend/app/routers/records.py`, `get_record`.

**Symptom.** Signed in as the buyer, with no grant of any kind against the
record:

```
GET /api/records/doc-ash-w2-008881
→ 200 {"record": {"merkle_root": "00eb716c…", "owner_msp": "ApexTextileMSP",
       "bucket": "ApexTextileMSP|Ashulia|safety_inspection|2026-05", …}}
```

**Why it matters.** Every neighbour of this endpoint scopes:
`GET /api/records` filters to records the caller holds a live grant against and
its docstring says so; `POST /api/records/{id}/screen` uses `scoped_records` and
404s; `/witness-requirement` and `/verify` both 404, and each has a test named
after the rule. The detail endpoint was the one that did not, so the whole
scoping story had a hole in the middle of it — and the record detail page is
exactly where a sceptical judge would point a URL by hand.

**Fix:** resolve through `scoped_records` and 404 with the reason, the same
shape the sibling endpoints use. Test added.

---

## 8. A revoked grant still read "granted" on the buyer's request row — FIXED

**Where:** `backend/app/routers/workspace.py`, `list_requests`.

**Symptom.** Revoke `g-br-002` on the chain, then ask as the buyer:

```
grant  g-br-002 → status "revoked", revoked_reason "test revoke"
request br-002  → status "granted", grant_id "g-br-002"
```

The buyer's portal printed a green *granted* seal for access that had been
withdrawn. Two screens in the same app disagreed about the same fact, and the
one facing the counterparty was the wrong one.

**Cause.** `BuyerRequest.status` is a stored copy of a decision. The grant is on
the ledger. Nothing kept the copy in step, and nothing could — a revoke happens
through a different endpoint that has never heard of the request.

**Fix:** stop treating the stored status as the whole answer. `list_requests`
resolves each answered request's grant on the ledger and returns `grant_status`
and `grant_revoked_reason` beside it; the interface shows *withdrawn* with the
reason. The stored status stays what the factory decided; the live state comes
from the chain, which is the authority.

---

## 9. A revoked grant could never be re-issued — FIXED

**Where:** `backend/app/routers/workspace.py`, `answer_request`.

**Symptom.** After revoking, answering the same request again:

```
POST /api/requests/br-002/grant → 409 {"detail": "already granted"}
```

and there was no other route to it, because the grant id was derived from the
request id (`g-{request_id}`) and `grant_access` refuses an id that already
exists. So a factory that revoked — deliberately, or by a misclick on a button
that asked for no confirmation — had permanently ended that request. The buyer
had to file a new one, and the factory had no control for it anywhere.

This is the "undo revoke" the walkthrough asked for, and it needs saying
precisely: **a revocation is not undone.** It stays on the chain with its
reason, its time and the identity that made it, because that is what a
revocation is for. What was missing is the ability to *issue access again* —
which is a new grant, visible as a new grant.

**Fix:** `answer_request` accepts a request whose current grant is no longer
active and writes a fresh grant under a versioned id (`g-br-002-r2`), leaving
the revoked one in the history. It still refuses while a grant is live, and now
says why.

---

## 10. A declined request was a dead end — FIXED

**Where:** `backend/app/routers/workspace.py`, `decline_request`.

**Symptom.** Decline sets `status = "declined"` and nothing can move it: every
other handler requires `pending`. A misclick ended the buyer's request forever,
with no recourse on either side. The endpoint also accepted a `reason` in its
body, parsed it, and threw it away, so the buyer was told nothing.

**Fix:** the reason is stored and shown to the buyer, and
`POST /api/requests/{id}/reconsider` returns a declined request to pending. This
is off-chain and stays off-chain, for the reason the module already gives: an
unanswered question is not a fact about the world and does not belong in an
append-only record. Only the answer does, and the answer is a grant.

---

## 11. Fatema had nowhere to do any of this — FIXED

**Where:** the factory's navigation, `components/Shell.tsx`.

**Symptom.** The factory is one half of every access decision in the product and
had no screen for it. What existed was an unlabelled panel at the bottom of the
shift log on the Loom Floor, below the fold, offering *Grant one field* and
*Decline* on pending requests only. Beyond that:

* no list of the 312 grants the factory has issued, and no way to reach one;
* revoking was possible only from a record's own page, one grant at a time, and
  only if you already knew which of 689 records it was on;
* the dashboard counts *"N grants you have revoked"* — a number with nothing
  behind it, on a page that cannot revoke;
* nothing at all for a declined request, or for one whose grant was revoked.

**Fix:** a new page, `/factory/access` — **Access** in the factory's
navigation, titled with the phrase the product already uses for this, *Who may
read a thread*. It holds:

* **Awaiting you** — pending requests, each with the record the grant would
  cover, *Grant one field*, and *Decline* with a reason.
* **Answered** — granted and declined requests with their live state read off
  the chain: *Revoke* with a reason, *Grant access again* once a grant has been
  revoked, *Reconsider* on a decline.
* **Grants you have issued** — all of them, filterable by status, buyer, field
  and record id, each revocable with a reason and linked to its record.

The Loom Floor's inbox keeps its two quick actions and now links here, and both
dashboard counts are links rather than decoration.

---

## 12. Revoke had no reason and no confirmation — FIXED

**Where:** `pages/RecordDetail.tsx`.

The button wrote a fixed string — `"Revoked by the record owner from the bolt
view"` — which records *where it was done*, not why, and fired on a single click
with nothing in between. That string goes on the ledger permanently and is shown
to the buyer whose access it ends.

**Fix:** revoking asks for a reason and a second press, on the record page and on
the new access page, and the text it writes is the one the user typed.

---

## 13. "Back" from a record sent everyone but the factory to the buyer's portal — FIXED

**Where:** `pages/RecordDetail.tsx`.

```js
to={role?.id === 'factory' ? '/factory/records' : '/buyer/portal'}
```

An auditor or a consortium administrator following a record link was returned to
a portal belonging to a different organisation. Same bug as #3, one page over.

**Fix:** the factory keeps its record list; everybody else goes to their own
`landing`, which the session already carries.

---

## 14. Nothing told the factory a request had arrived — FIXED

**Where:** `backend/app/routers/workspace.py`.

The seed ships a notification reading *"Primark Sourcing requested payroll access
for 2027-02"* addressed to Apex, so the pattern and the bell in the sidebar both
existed — but a request made through the running app wrote none. Nor did a
grant, a decline or a revocation write one back to the buyer. The only signal
that anything had happened was a count on a dashboard the user had to think to
open.

**Fix:** `notify()` in `db.py`, called on request, grant, decline, reconsider and
revoke. The factory's bell lights when a buyer asks; the buyer's lights when the
factory answers, and again if the access is later withdrawn.

---

## 15. Six stylesheets paint with variables that were never declared — FIXED

**Where:** `styles/tokens.css`, and the sixteen `var(--rule)` call sites in
`records.css`, `registry.css`, `upload.css`, `states.css`, `chainstatus.css`
and `mechanisms.css`.

**Symptom.** Panels with no frame and tables with no rules: the Bolts filter
bar, the model registry's cards, the upload preview, the detector panel, and —
worst, because they appear on every screen in the product — the loading, empty
and refusal states, which are supposed to be a bordered block and were bare text
on the page ground.

**Cause.** `--rule`, `--rule-faint` and `--paper-2` are used and were never
declared. A `var()` with no declaration and no fallback makes the whole
declaration invalid at computed-value time, so those borders and backgrounds
were not faint — they were absent. The token file's own opening line says
*"Every colour in this application resolves to a variable declared here"*, and
for three of them that had stopped being true.

The same for `.dim`, used twenty-five times across the application and defined
in exactly three page-scoped table rules. Everywhere else it did nothing, so the
quiet half of a line — a timestamp, a block number — was set at the same weight
as the loud half. And `.visually-hidden`, used for a table column whose header
is noise on screen and required off it, was never defined at all.

**Fix:** declare the three tokens in `tokens.css`, named by role rather than by
colour, and define `.dim` and `.visually-hidden` in `base.css`. `.dim` resolves
against its ground the same way `--brass-type` already does — `#6f6a5e` is
3.3:1 on indigo, so the dark islands take the lifted value — and the three
page-scoped rules still win on specificity where a page wants something else.

---

## Not a bug (checked and cleared)

**The Continuity Gate benchmark table** on `/model/gate/:id` looks clipped at the
right edge on a narrow window, but `.gptable-wrap` carries `overflow-x: auto`
and scrolls correctly; `document.body.scrollWidth` equals the viewport.

**Seeded grants outnumbering real ones** is demo-data design, not a defect.
Worth knowing before the finals: the buyer starts holding 259 grants, so the
request→grant flow has to be demonstrated on a *new* request to be legible —
which is exactly why bug 6 mattered.

**Sealing a record that the witness rule has sampled is refused**, and that is
the mechanism rather than a fault. `/factory/upload` asks who would have to
counter-sign *before* the button is pressed and says plainly that the
counter-signature cannot be produced from the browser. The refusal is real and
the screen predicts it.

**Revocation being permanent** is deliberate and is not what bug 9 was about.
The contract's own words: *"Revoke a grant. Permanent and attributable, which is
the point."* What was missing was re-issue, not erasure.

---

## Still open — a decision, not a bug

The record-type list is maintained in **four** parallel places:
`model/chaincode/doccustody.py` (`VALID_TYPES`, the authority),
`model/fabric/chaincode/doccustody.js`, `backend/app/corpus.py` (`LEDGER_TYPES`),
and `frontend/src/lib/api.ts` (`RECORD_LABEL`). No endpoint exposes the accepted
types, so the frontend cannot derive them. Worth unifying after the finals, not
days before it.

Separately: the corpus genuinely generates `production_output` documents (~20% of
it) and the seed counts and excludes them. Whether the chaincode *should* accept
a sixth type is still an open question; fix 2 only stops the UI promising
something the contract refuses.

A grant whose `expires_at` has passed still reports `status: "active"` in
listings — the contract only ever writes `active` or `revoked`, and expiry is
enforced at use, by `record_verification`. Every seeded grant runs to 2028 so
nothing on screen is wrong today, but a listing that says "active" for a grant
the contract will refuse is a claim that will eventually be false. It wants a
derived status, which is a contract change.

## What was fixed, and how it was checked

| # | Bug | Files | Verified |
|---|---|---|---|
| 1 | Detector paragraph overflow | `Screening.tsx`, `mechanisms.css` | height 507px → 156px, 9 flex items → 2, `scrollWidth == clientWidth` |
| 2 | `production_output` mismatch | `lib/api.ts` | dropdown returns exactly the five `VALID_TYPES` |
| 3 | `/verify` back link | `VerifyResult.tsx` | header and footer both → `/buyer/portal` when signed in |
| 4 | Grant rows never named the document | `Lightbox.tsx`, `lightbox.css` | row reads `cas_number · Chemical Inventory · July 2026 · … · doc-gaz-w2-010295` |
| 5 | Reopened period could not be re-sealed | `SealActions.tsx`, `Upload.tsx`, `mechanisms.css` | reopen → commit → amend driven from the UI; seal goes to version 2, count 6, 1 amendment |
| 6 | New grant invisible to the buyer | `Lightbox.tsx`, `VerifyResult.tsx` | `g-br-002` is first in both lists straight after it is issued |
| 7 | Record detail unscoped | `routers/records.py` | buyer reading a record it holds no grant on → 404, test added |
| 8 | Revoked grant read "granted" | `routers/workspace.py`, `lib/api.ts`, `Lightbox.tsx` | request row reads *withdrawn* with the reason the moment the grant is revoked |
| 9 | Revoked access could not be re-issued | `routers/workspace.py` | second grant on `br-002` writes `g-br-002-r2`; the revoked one stays on chain |
| 10 | Declined request was a dead end | `routers/workspace.py`, `db.py` | `POST /requests/br-003/reconsider` → pending, decline reason stored and shown |
| 11 | Factory had no access screen | `pages/Access.tsx`, `Shell.tsx`, `App.tsx`, `LoomFloor.tsx` | `/factory/access` lists 3 requests and 313 grants, all four actions exercised |
| 12 | Revoke had no reason | `RecordDetail.tsx`, `Access.tsx` | the reason on the chain is the one typed |
| 13 | Record back link | `RecordDetail.tsx` | auditor → `/auditor/workspace`, consortium → `/governance` |
| 14 | No notification on a request | `routers/workspace.py`, `routers/records.py`, `db.py` | bell shows the request to Apex and the answer to Primark |
| 15 | Undeclared CSS variables | `tokens.css`, `base.css` | 16 `var(--rule)` call sites resolve; states, tables and panels have their frames back |
