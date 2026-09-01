# Handoff prompt — new ledger capabilities to expose in the API and the UI

> Paste everything below the rule into the other Opus 5 session.

---

You are working on **Breadcrumbs**, a permissioned-blockchain prototype for verifiable
garment-factory compliance records (Blockchain Olympiad Bangladesh submission). The repo
has `model/` (the ledger + chaincode, Python), `backend/` (FastAPI + SQLite wrapping
`model/`, never reimplementing it), and `frontend/` (React + TypeScript + Vite). Your job
is the **backend endpoints and the frontend components** for four new ledger mechanisms
that were just built and tested. The ledger side is finished and has 138 passing tests —
do not modify `model/`. Wrap it.

**House rules that already govern this codebase and must govern your work.** The backend
never reimplements ledger logic; it calls chaincode through `backend/app/ledger_service.py`.
Authorization goes through the positive capability table in `backend/app/config.py` and
`require_capability()` — a handler must name a capability, never write an ad-hoc
`if role ==` check (this is audit finding F-5 and it must not regress). Every guarantee the
interface asserts needs a test that tries to break it. And the UI must never overstate:
where a mechanism is off, or a proof is partial, the screen says so.

## What was added

**1. Period seals and completeness proofs.** A *bucket* is `owner_msp|site|record_type|period`.
`seal_period` closes a bucket: the contract enumerates every record the ledger holds for it,
refuses if the declared list omits any, and commits a count plus a Merkle root over the
sorted record ids. After sealing, `commit_record` into that bucket is refused; a late record
needs `amend_seal`, which keeps the old count and root in an amendment history and demands a
written reason. `check_completeness(owner_msp, site, record_type, period, disclosed_record_ids)`
returns `{sealed, complete, sealed_count, disclosed_count, sealed_root, computed_root,
amendment_count, reason}`. This is the headline claim: **other systems prove a record is
genuine; this proves nothing is missing.** A factory disclosing 4 of 5 sealed registers is
caught by arithmetic, not by trust.

**2. Attesting witnesses.** A second organisation counter-signs a record at capture. The
witness is *assigned, not chosen*: `witness_requirement(record_id, record_type, owner_msp)`
returns `{in_force, required, round_id, witnesses[], pool_size}`. The assignment comes from a
commit–reveal seed round (`open_seed_round` → `commit_seed_share` → `reveal_seed_share`), so
no member controls it. `commit_record` now accepts `attestations: [{witness_msp, check_code,
attested_at, certificate_pem, signature}]` and refuses unassigned witnesses, duplicate
attestations, self-signed impersonation, and signatures lifted from another document.
`check_code` is one of `format_only`, `sample_row_recompute`, `source_system_readback`,
`physical_presence` — increasing evidentiary weight, and the UI should show which was claimed.
**Until a seed round closes the rule is not in force**, and `in_force: false` must be visible
on screen rather than silently implying a guarantee that is off.

**3. The RSA accumulator (`anchor` chaincode).** One 3072-bit integer commits the whole record
set. `advance_epoch` folds a batch of committed records and seals into it with a proof of
exponentiation — one ledger write per epoch instead of one per document. Verification of an
epoch is **constant time whatever the batch size** (measured: 4.4 ms for any n, against 338 ms
recomputing). Endpoints to expose: `get_state` → `{value_hex, epoch, size}`, `get_group` →
parameters plus the ceremony transcript, `get_digest(epoch)`, `list_digests`,
`is_anchored(prime_hex)`. The accumulator also produces **non-membership witnesses** —
cryptographic proof that a claimed certificate was *never* committed, which no Merkle tree can
do. That deserves its own screen: an auditor pastes a certificate reference and gets back
"never committed", proved.

**4. The delay beacon.** `publish_beacon` attaches a verifiable-delay-function proof to an
epoch, bounding how fast history can be manufactured. Show `iterations` and verification
status on the epoch timeline.

## The thing the UI must get right

`model/anchoring.py:verify_record` does **three independent checks** and the interface must
render all three separately, not collapse them into one green tick:

1. the ledger holds the record with this Merkle root,
2. the accumulator witness verifies,
3. the prime appears in the anchored index.

The reason is specific. The RSA modulus comes from a trusted-dealer ceremony, so whoever holds
the factorisation *can* forge check 2 — there is a passing test that does exactly that. Checks
1 and 3 are what make the forgery fail anyway. A UI that shows one combined "verified" badge
throws away the entire defence and misrepresents the guarantee. Show three rows, each with its
own state, and a short explainer.

## Backend work

Add routers for: seals (`POST /api/seals`, `POST /api/seals/{bucket}/amend`,
`GET /api/seals`, `POST /api/completeness`), witnesses (`GET /api/records/{id}/witness-requirement`,
`POST /api/seed-rounds`, `POST /api/seed-rounds/{id}/commit`, `POST /api/seed-rounds/{id}/reveal`),
and the accumulator (`GET /api/anchor/state`, `GET /api/anchor/epochs`,
`GET /api/anchor/epochs/{n}`, `POST /api/anchor/epochs`, `POST /api/anchor/beacon`,
`POST /api/records/{id}/verify`, `POST /api/anchor/non-membership`).

Scoping rules, and get these right because the previous version of this API leaked: a factory
sees its own seals and records; a buyer or auditor sees only what it holds a live grant
against; the regulator sees accumulator state, epochs and digests — which are consortium-wide
facts — and **no** records, seals or grants. Add the new capabilities to the table in
`config.py` rather than special-casing. Big integers must cross the wire as **hex strings**,
never JSON numbers: a 3072-bit value is silently destroyed by every JSON parser that maps
numbers to doubles, and the frontend has one.

## Frontend work

Six components. **Period Seal card** — count, root, amendment history as a timeline, and a
prominent state for "sealed" versus "amended 3 times", because a high amendment rate is itself
a signal. **Completeness Checker** — the buyer pastes or selects what it was given and sees the
arithmetic: sealed 5, disclosed 4, one withheld, with the two roots shown differing. Make this
one good; it is the demo moment. **Witness panel** — who was assigned, what they claimed to
have checked, and whether the rule is in force. **Epoch timeline** — accumulator value, size,
element count, beacon iterations per epoch. **Three-check verification panel** as described
above. **Non-membership screen** — proof of absence.

Match the existing design tokens in `frontend/src/styles/`. Write the failing-path states
first: a withheld record, an unwitnessed commit, a stale witness, a beacon that claims less
work than agreed. Those are the screens that make the system's claims legible, and they are
the ones a judge will ask to see.
