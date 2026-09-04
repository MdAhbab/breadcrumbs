# Using the app

What each screen is called, what it does, and the order the work happens in. The
in-product walkthrough (`Show me how it works`, on the home page) covers the same
ground by driving the real screens; this is the written version, for anyone who
would rather read it or is looking for one particular thing.

Every screen name below is the name on the navigation. Where a name changed, the
old one is in brackets — the previous set described the product's own model of
itself rather than the job being done, and a walkthrough or a guide naming a
button that no longer exists is worse than none.

---

## The workflow, in four steps

1. **The factory files a document.** The file stays in the factory. Only its
   fingerprint goes onto the shared record, with the kind of document and the
   month it covers.
2. **A buyer asks for one figure.** One column, one kind of document, one month,
   with a reason. Never the file.
3. **The factory decides.** Releasing a column writes a permission that names one
   column of one document and expires on a date the factory sets. It can be
   withdrawn later, with the reason recorded.
4. **The buyer or auditor checks it** — and checks the month is complete. The
   figure is checked against the fingerprint published months earlier; the month
   is checked against the count fixed when it was closed.

Reading and proving are different acts, and the product keeps them apart
everywhere:

* **Opening a file is a read.** No transaction is proposed, no receipt is
  written, and the shared record cannot tell you did it.
* **Checking a figure is a transaction.** It writes a receipt under your name
  that the factory — and anyone you send it to — can see for good.

---

## Factory (compliance staff)

| Screen | What it is for |
|---|---|
| **Dashboard** | Activity, and what is waiting on you. |
| **Upload a document** | File a wage sheet, inspection or inventory. Fingerprinted in the browser; only the fingerprint is sent. |
| **My documents** | Everything you have filed, and the inside of any of it. |
| **Sharing & permissions** *(was "Who can see what")* | Requests waiting on you, what you decided, every permission you have issued, and every check anyone has run against your documents. |
| **Month-end closing** *(was "Closed months")* | Close a month, reopen one, correct one, and see who holds a copy of what. |
| **Transaction history** *(was "Ledger")* | The blocks themselves. |

**Sharing & permissions** opens with a tile per organisation: how many live
permissions each holds, across how many documents, and how many have ended.
Pressing a tile filters the table below it, so the summary and the detail are the
same control and cannot disagree. Each row of the three lists keeps its own
draft — a reason typed against one refusal never follows you onto another.

**Month-end closing** opens its forms in a panel at the right rather than
unfolding them inside the row. Closing a month lists every document it is about
to seal in before you confirm: the count and a root over those identifiers go
onto the shared record, and that is what a buyer later checks a disclosure
against. Undoing it means a reopening, which is permanent and counted on the
seal.

---

## Buyer / brand

| Screen | What it is for |
|---|---|
| **Request documents** *(was "Request data")* | Ask a factory for one or more figures, with a reason and an end date. |
| **Monthly completeness** *(was "Check for gaps")* | Confirm a month is complete: closed at five documents, shown four. |
| **Verify a document** *(was "Check a value")* | Open what you hold and check it. |
| **Transaction history** | The blocks themselves. |

Each permission in the list has **Open the file**, which goes straight into that
document — the columns released to you, padlocks over everything else. The link
carries the permission, and the verify screen resolves it to the document behind
it, so it always opens the one you pressed.

**Verify a document** is in four parts, in the order they are needed: which
document, what you hold on it (which columns, until when), the document itself
with a check on each row, and what checking leaves behind. Following a link to a
permission that has since been withdrawn says so rather than quietly opening a
different file.

---

## Auditor

| Screen | What it is for |
|---|---|
| **My audit checks** *(was "Checks to run")* | Every permission you hold, and whether it has been checked. Run the batch, then sign the attestation. |
| **All documents** | Every document on the network. An auditor does not ask. |
| **Monthly completeness** | The same completeness check a buyer runs. |
| **Verify a document** | Open one document and check it row by row. |
| **Transaction history** | The blocks themselves. |

Two different signatures live in this workspace, and they are not the same act:

* An **attestation** covers a batch — everything examined in a sitting — and
  names no single document. It is refused if anything in the batch has no
  verification receipt on the record.
* A **confirmation of review** names one document. It is signed at the foot of
  that document, and is generated as a document of its own: its own reference,
  the reviewer's name and organisation, what they concluded, and the receipts on
  the record that it rests on. It can be handed to somebody who cannot open the
  register itself.

A confirmation is generated once per reviewer per document. Signing the same
document again is the same claim with a later date on it, so the API refuses it
and points at the one that already stands. A different organisation reviewing
the same document gets its own — two independent reviewers agreeing is a fact
worth being able to show. A buyer can sign one too, as a commercial
acknowledgement rather than an audit opinion; the confirmation says which. The
factory that owns a document cannot sign one about it, and can see every
confirmation signed about it.

Confirmations you have signed are collected in **My audit checks**, beside the
attestation block.

---

## Trade body (consortium)

| Screen | What it is for |
|---|---|
| **Members & voting** *(was "Members & proposals")* | Admit and suspend members by vote. A carried motion is executed on the record. |
| **AI model approvals** *(was "Model approvals")* | The Continuity Gate: what a candidate detector did to problems already solved. |
| **AI model history** *(was "Model history")* | Every version, approved and refused, with the reason. |
| **Tamper check** | The accumulator: membership, absence, and the delay beacon. |
| **Transaction history** | The blocks themselves. |

## Regulator (observer)

| Screen | What it is for |
|---|---|
| **Dashboard** | Governance events and totals. No factory document at all. |
| **Tamper check** | Check nothing has been altered, and prove a document was never filed. |
| **Transaction history** | The blocks themselves. |

The blocked parts of the regulator's screens are still drawn, with the reason
written on them. Hiding them entirely would teach nobody where the line sits.

---

## The two buttons on a document

At the top of any document you can open:

* **`check`, on a row** — takes the figures released to you on that row, works
  the file's fingerprint out again from them, and compares it with the one the
  factory published. Matching means those figures are exactly what was
  published.
* **`Check every row against the ledger`** *(was "Check all N rows")* — the same
  check, from the top, once per row. It writes one receipt per figure checked,
  under your name, and the panel above the table says how many that will be
  before you press it.

At the foot of the same screen is the confirmation of review described above.
