# Bugs found during the 2026-09-03 walkthrough

**Status: all three fixed.** Verified live in the running app; 246 tests pass,
`tsc --noEmit` clean, production build clean. Not committed.

Found by driving the running app as each of the five roles. Both are reachable
by a judge clicking around at the finals.

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

## Not a bug (checked and cleared)

The Continuity Gate benchmark table on `/model/gate/:id` looks clipped at the
right edge on a narrow window, but `.gptable-wrap` carries `overflow-x: auto`
and scrolls correctly; `document.body.scrollWidth` equals the viewport. Working
as intended.

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

## What was fixed, and how it was checked

| # | Bug | Files | Verified |
|---|---|---|---|
| 1 | Detector paragraph overflow | `Screening.tsx`, `mechanisms.css` | height 507px → 156px, 9 flex items → 2, `scrollWidth == clientWidth` |
| 2 | `production_output` mismatch | `lib/api.ts` | dropdown now returns exactly the five `VALID_TYPES` |
| 3 | `/verify` back link | `VerifyResult.tsx` | header and footer both → `/buyer/portal` when signed in |

Fix 2 also silently repaired a second instance of the same bug: `Lightbox.tsx`
builds the buyer's access-request type select from the same `RECORD_LABEL` map,
so a buyer could previously request access to a record type the ledger can never
hold.

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
