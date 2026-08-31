# Breadcrumbs — security and engineering audit

**Scope:** `model/` (ledger, chaincode, Merkle, learning plane) and `backend/`.
**Method:** code review plus written proof-of-concept attacks against each claimed
guarantee. Nothing below is theoretical — every finding marked *confirmed* was
reproduced by running it before the fix, and every fix has a regression test that
fails against the old code.

**Result:** 5 serious findings, all fixed. Two of them defeated the project's
headline claim outright. 91 tests now pass, up from 69.

The remaining gaps in §3 are real and mostly cannot be closed on a laptop. They
are written down so nobody is surprised by them on stage.

---

## 1. Summary

| # | Finding | Severity | Status |
|---|---|---|---|
| F-1 | Endorsement signatures verified against a caller-supplied key | **Critical** | Fixed |
| F-2 | One actor could forge every organisation's Gate evaluation | **Critical** | Fixed |
| F-3 | No transaction replay protection | High | Fixed |
| F-4 | Blocks could mix channels, breaking confidentiality | High | Fixed |
| F-5 | Regulator and buyer could read every factory record via the API | High | Fixed |
| F-6 | Certificate expiry check was unreachable | Medium | Fixed |
| F-7 | Every write carried one hardcoded timestamp | Medium | Fixed |
| F-8 | Inconsistent refusal for a malformed MFA code | Low | Fixed |
| F-9 | `flwr` declared as a dependency but never imported | Low | Documented, §3.1 |

---

## 2. Findings

### F-1 — Endorsements were verified against a key the endorser supplied · **Critical** · fixed

**Where:** `model/ledger/endorsement.py`, `EndorsementValidator.valid_orgs`.

The validator loaded the public key *out of the endorsement itself*, checked the
signature against it, and then only checked that the MSP ID string appeared in
the known-organisations table. It never checked that the key belonged to a
certificate issued by that organisation.

A signature proves that somebody holds some private key. It says nothing about
who. Binding the key to a certificate is the entire step that turns a signature
into an identity, and it was missing.

**Confirmed by:** attaching a freshly generated keypair labelled
`BVCertificationMSP` to a transaction endorsed only by Apex. The `AND(Apex, BV)`
policy was satisfied and the transaction committed `VALID`.

```
policy AND(Apex, BV) -> valid=True code=VALID
*** FORGED ENDORSEMENT ACCEPTED ***
```

**Impact:** every endorsement policy in the system was decorative. Any party able
to submit a transaction could satisfy any policy alone.

**Fix:** an `Endorsement` now carries `certificate_pem` instead of a raw public
key. `MSP.public_key_for()` resolves it — checking the issuer chain, the CA
signature, revocation, validity dates, and that the certificate's OU actually
names the organisation it claims — and only the key from that validated
certificate is used to check the signature.

**Regression test:** `test_an_endorsement_key_must_be_bound_to_a_certificate`.

---

### F-2 — A single actor could forge every Gate evaluation · **Critical** · fixed

**Where:** `model/chaincode/fedmodel.py`, `evaluate_gate`; mirrored in
`model/fabric/chaincode/fedmodel.js`.

The same flaw as F-1, in the contract that matters most. Gate submissions carried
a bare `public_key`, and the contract verified each signature against the key in
the submission it was checking.

**Confirmed by:** generating three unrelated keypairs, labelling them
`ApexTextileMSP`, `NoorGarmentsMSP` and `BVCertificationMSP`, and signing
flattering accuracies for a model that had actually collapsed from 91.6% to
52.9% on wage-register inconsistency.

```
true wage accuracy 52.9%, claimed 92.0%
outcome=promote  endorsers=['ApexTextileMSP','BVCertificationMSP','NoorGarmentsMSP']
*** A SINGLE ACTOR PROMOTED A FORGETFUL MODEL ***
```

**Impact:** this is the one that matters. The project's central claim — *"no
single participant, including whoever runs the aggregation server, can promote a
model alone"* — was false. The Continuity Gate, the report's main contribution,
could be satisfied unilaterally by exactly the party it exists to constrain. Had
a judge probed this, the entire submission would have collapsed on its own
headline.

**Fix:** submissions carry `certificate_pem`; the contract resolves it through
`ctx.msp.public_key_for()` before checking any signature. The JavaScript
chaincode was fixed identically, using `crypto.X509Certificate`, and additionally
checks the certificate's OU against the claimed MSP and its validity window.

**Regression tests:** `test_one_actor_cannot_forge_every_organisations_evaluation`
and `test_a_real_certificate_from_the_wrong_organisation_is_rejected` — the second
covers the subtler case of a genuine member's certificate presented under another
organisation's name.

---

### F-3 — No transaction replay protection · High · fixed

**Where:** `model/ledger/network.py`, `Network.commit`.

Nothing tracked which transaction ids had been committed. Replays were caught
only *incidentally*, by the MVCC read-set check, and only when a transaction
happened to read a key it also wrote.

**Confirmed by:** a contract performing a blind write — no reads at all. The
identical transaction, resubmitted byte for byte, committed a second time.

```
read_set size = 0   first=VALID  replayed=VALID
```

**Impact:** any transaction that writes without reading could be applied twice by
anyone who observed it. For this codebase that is a latent rather than an
exploited hole — every current chaincode function happens to read before writing
— but it is one blind write away from being live, and "we were lucky" is not a
control.

**Fix:** each channel keeps `committed_tx_ids`; a repeat is marked
`DUPLICATE_TXID` and recorded in the block rather than applied.

**Regression test:** `test_a_transaction_cannot_be_committed_twice`, which asserts
`read_set == []` first so it genuinely exercises the new check.

---

### F-4 — Blocks could mix channels · High · fixed

**Where:** `model/ledger/orderer.py`.

The ordering service held one shared pending queue. `Network.commit` picked a
channel by reading `orderer._pending[0].channel` — a private attribute — and then
cut a batch that could contain transactions from *any* channel.

**Confirmed by:** submitting one document-channel and one model-channel
transaction, then cutting one block:

```
block contains channels: {'documents-apex-primark', 'model-channel'}
```

**Impact:** channels are the confidentiality boundary. The report's argument is
that a second buyer holds no copy of another buyer's data — "not
encrypted-but-present, absent". A block delivered to a channel's peers carrying
another channel's transactions breaks precisely that, and it is the guarantee the
whole Plane A story rests on.

**Fix:** one queue per channel; `cut()` takes the channel as an argument; a block
belongs to exactly one channel by construction. The private-attribute reach into
`_pending` is gone.

**Regression test:** `test_a_block_never_mixes_channels`.

---

### F-5 — The API served factory records to everyone · High · fixed

**Where:** `backend/app/routers/records.py`.

`GET /api/records` had no authorization check and no scoping. Any signed-in
caller received every committed record on the channel.

**Confirmed by:**

```
regulator GET /api/records -> 200, 5 factory records returned
buyer     GET /api/records -> 200, 5 records (unscoped)
```

**Impact:** the regulator screen's entire premise is that it shows aggregate
governance data and no factory data — the design specification even requires the
restriction to be visible on screen. The API contradicted it. A judge with
`curl` and the demo's own token would have found this in a minute.

**Fix:** a capability table in `backend/app/config.py` replaces ad-hoc role
checks. Reads and writes both go through `require_capability()`. The regulator
holds no `read_records` or `read_grants` capability at all. Listings are scoped:
a factory sees its own records; a buyer or auditor sees only records it holds a
live grant against.

Doing it as a positive capability table rather than scattered `if role ==` checks
matters — the original gap existed because a new endpoint was written and nobody
remembered to add a check. Now a handler has to name a capability.

**After:**

```
regulator  /records -> 403   /grants -> 403
buyer      /records -> 200 (1)   /grants -> 200 (1)
factory    /records -> 200 (5)   /grants -> 200 (4)
```

**Regression tests:** `backend/tests/test_api.py` — five tests covering the
regulator's denials, what it *can* still see, and buyer/factory scoping.

---

### F-6 — The certificate expiry check could never fire · Medium · fixed

**Where:** `model/ledger/identity.py`.

The check compared `not_valid_after` against the fixed issuance epoch
(2026-01-01) rather than the clock. Certificates are issued epoch + 730 days, so
the branch was unreachable: an expired certificate would have been accepted
indefinitely.

**Fix:** compares against `datetime.now(timezone.utc)`, and also rejects
not-yet-valid certificates. The clock lives in the MSP, never in chaincode —
a contract that reads a clock is non-deterministic and two endorsers would
disagree.

**Regression test:** `test_an_expired_certificate_is_rejected`, which injects
both a past and a future `now`.

---

### F-7 — One hardcoded timestamp for every write · Medium · fixed

`NOW = "2026-08-31T12:00:00Z"` as a module constant in two routers. Every record
committed through the API shared a commit time, and the grant-expiry comparison
in `record_verification` was meaningless.

**Fix:** a `now()` helper per router. The value still reaches the contract as an
*argument* — the contract must never read a clock itself.

---

### F-8 — Inconsistent refusal for a bad MFA code · Low · fixed

An empty code hit Pydantic's `min_length` and returned a generic 422; a
five-digit code reached the handler and returned the designed sentence with a
400. One mistake, two experiences. The length constraint was removed so every bad
code gets the same guidance.

---

## 3. What is left — gaps not closed

These are ordered by how likely a judge is to ask.

### 3.1 Flower is declared but never used — *fixable on any machine*

`flwr` is in the dependencies and the report names it as the federation
framework, but nothing imports it. `model/ai/federated.py` implements the
federated loop directly.

That is defensible — the loop is real, and writing it out makes the clipping,
noising and trimmed-mean steps visible rather than hidden in a strategy class —
but the paper says Flower, so either the code or the paper should change. The
honest options are to write a `flwr` `Strategy` wrapping the existing aggregation
(about half a day, no new concepts), or to amend the report. **Do not leave it
as it is**; a reviewer who greps for `flwr` will find nothing.

### 3.2 Blocks are not signed by the orderer — *fixable, ~2 hours*

Blocks carry a `proposer` field but no signature over the header. In Fabric the
ordering service signs each block, which is what stops a peer fabricating history
that never went through consensus. Chain integrity here rests on the hash links
and the persisted hashes, which detects *tampering* but not *fabrication* by
whoever controls the store.

### 3.3 Range queries have no phantom-read protection — *known Fabric limitation*

`Context.range()` records the versions of keys it *found*. A concurrent
transaction inserting a new key matching the same prefix is invisible to
validation. Fabric solves this by recording range-query bounds in the read set.
Currently no chaincode function makes a decision based on a range result, so this
is latent — but `list_*` functions are one refactor away from doing so.

### 3.4 The submitter does not sign the transaction — *fixable, ~1 hour*

Only endorsers sign. The submitter's identity is inside the signed payload, so it
cannot be swapped without invalidating the endorsements, but there is no direct
proof the submitter authorised the proposal. Fabric has the client sign it.

### 3.5 Single-node ledger, no external anchor — *inherent to the demo*

Everything runs in one process against one SQLite file. An attacker with write
access to both the process memory and the database could rewrite history
consistently. Real Fabric distributes this across organisations; that is the
point of `model/fabric/` and it needs your PC.

### 3.6 No secure aggregation — *by design, and disclosed*

The report states the conflict: secure aggregation, robust averaging and
contribution scoring cannot all three hold, and the first deployment gives up
secure aggregation. The code matches the report. This is a disclosed limitation,
not a defect — but be ready to say which two you kept and why.

### 3.7 The memory bank's noise is not differential privacy — *by design, disclosed*

`MemoryBank.privacy_note()` returns the exact sentence, and the API serves it
from there rather than restating it, so no interface can quietly soften it. Still
a real limitation: no sensitivity bound, no budget, and released variances and
counts carry no noise at all.

### 3.8 Frontend is a scaffold — *the largest remaining build*

Routes, tokens, shell and typed API client exist; 26 screens are specified in
`frontend/designs_instructions.md` and not built. The API behind them runs.

### 3.9 Operational hardening not done — *needed only for a real deployment*

No rate limiting, no pagination on list endpoints, no JWT revocation (`jti`), no
security headers, no HTTPS enforcement, no audit log of API access separate from
the ledger. All are ordinary production work and none affect a demo.

### 3.10 Fabric assets never executed

Unchanged from what you already know: `model/fabric/` is written, its hashing is
byte-identical to the Python side, and no peer has ever run it. The README says
so. This is the first thing to do on your PC.

---

## 4. What changed

**New security tests (7):** certificate binding for both the ledger and the Gate,
a genuine certificate presented under the wrong organisation, transaction replay
of a blind write, channel isolation, certificate expiry in both directions.

**New API tests (16):** authentication, the full authorization matrix, selective
disclosure over HTTP, out-of-scope refusal, ledger integrity.

**Packaging:** `pyproject.toml` with `ml` / `api` / `dev` extras, so the ledger
can be installed and tested without pulling ~2 GB of PyTorch. `pip install -e .`
replaces the `sys.path` hack. `Makefile` and `SETUP.md` for a clean clone.

**Lint:** ruff configured and applied; 56 of 59 findings fixed. `zip(..., strict=True)`
where a length mismatch would silently drop a participant from an aggregation
round, plus an explicit length check in `weighted_average`.

**Removed:** `REVIEW.md` from the repository root, and its references from `README.md`.

---

## 5. Verifying this audit

```bash
cd "Breadcrumbs Project"
make setup
make test          # 91 tests
make demo          # the end-to-end cycle
make lint
```

To watch the fixed attacks fail, run the regression tests by name:

```bash
.venv/bin/python -m pytest -k "forge or replay or mix_channels or expired or regulator" -v
```

---

## 6. The one thing to take from this

Two of these findings meant the system's headline guarantee was false while the
demo appeared to work perfectly. Both were in signature verification, both looked
correct on a casual read, and neither would have been caught by any test that
only exercises the happy path.

The tests that caught them are the ones that name an attacker and try the attack.
That is the pattern worth keeping as the frontend gets built: for every guarantee
the interface asserts, write the test that tries to break it.
