import { Check, Download, FileText, PenLine } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import {
  ApiError, api, shortMsp,
  type RecordReviews, type ReviewConfirmation, type ReviewOutcome,
} from '../lib/api';
import { dateTime, longDate } from '../lib/format';
import { useApi, type Query } from '../lib/useApi';
import { Failed, Result } from './states';
import { Seal } from './ui';
import './review.css';

/**
 * Counter-signing one document, and the confirmation that comes out of it.
 *
 * An auditor could sign a batch attestation covering everything it checked that
 * day and naming no document at all, and a buyer could sign nothing whatever.
 * So the one question anybody actually asks about a particular register —
 * has somebody independent looked at this one, and who — had no answer in the
 * product, only a claim spread thinly across a batch.
 *
 * Signing here mints an individual confirmation: its own reference, the name of
 * the person signing, what they concluded, and the verification receipts on the
 * ledger that it rests on. It is a document in its own right, which is the
 * point — it can be handed to somebody who cannot open the register itself and
 * still be followed back to the chain.
 *
 * It is minted once per reviewer. A second confirmation of the same document
 * from the same organisation is the same claim with a later date on it, and the
 * API refuses one; a different reviewer gets their own, because two independent
 * reviewers agreeing is a fact worth being able to show.
 *
 * The name on the form is the one the API resolved from the token, not the one
 * this browser happens to be holding. A signature panel showing a name the
 * server would not write is making a promise it does not keep.
 */
export function ReviewSignoff({ recordId }: { recordId: string }) {
  const reviews = useApi(() => api.recordReviews(recordId), [recordId]);
  return <ReviewSignoffPanel recordId={recordId} query={reviews} />;
}

/**
 * The same panel, over reviews a page above it is already holding.
 *
 * The record page shows a count of these confirmations next to the witness
 * attestations, and a count that came from a second copy of this query would go
 * stale the moment somebody signed — the panel would fill in and the count
 * beside it would still read nothing, which is the very complaint this whole
 * change is about. So the page owns one query and both panels read it.
 */
export function ReviewSignoffPanel({
  recordId, query,
}: {
  recordId: string;
  query: Query<RecordReviews>;
}) {
  return (
    <section className="rev">
      <Result query={query} pendingLabel="Looking for a confirmation of review">
        {(data: RecordReviews) => (
          <Panel data={data} recordId={recordId} onSigned={query.reload} />
        )}
      </Result>
    </section>
  );
}

const OUTCOME_TONE: Record<ReviewOutcome, 'sealed' | 'pending' | 'broken'> = {
  accepted: 'sealed',
  qualified: 'pending',
  rejected: 'broken',
};

const OUTCOME_WORD: Record<ReviewOutcome, string> = {
  accepted: 'Reviewed and accepted',
  qualified: 'Accepted with reservations',
  rejected: 'Not accepted',
};

/**
 * What "say something" means, and it is the API's rule rather than a second
 * opinion about it.
 *
 * This was a minimum of twelve characters, which is not a rule anybody would
 * state out loud: "it is good" is a complete finding and is ten characters, so
 * the button sat there disabled while the box plainly had writing in it. Words
 * are the unit a person is actually thinking in, and the count is now shown
 * while it is short rather than only implied by a button that will not press.
 */
const MINIMUM_WORDS = 3;

const wordsIn = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;

function Panel({
  data, recordId, onSigned,
}: {
  data: RecordReviews;
  recordId: string;
  onSigned: () => void;
}) {
  const [outcome, setOutcome] = useState<ReviewOutcome>('accepted');
  const [statement, setStatement] = useState('');
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const others = data.reviews.filter((r) => r.reviewer_msp !== data.you.msp_id);
  const written = wordsIn(statement);
  const short = written < MINIMUM_WORDS;

  const sign = async () => {
    setBusy(true);
    setFailure(null);
    try {
      await api.confirmReview(recordId, { outcome, statement: statement.trim() });
      setStatement('');
      onSigned();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'the confirmation was not written'));
      // A refusal here is almost always "you have already confirmed this one",
      // and the confirmation that already stands is the answer to it. Reloading
      // puts it on screen instead of leaving the reader with a red box.
      onSigned();
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <header className="rev__head">
        <div>
          <h3 className="rev__title">Confirmation of review</h3>
          <p className="small rev__sub">
            {data.yours
              ? 'You have confirmed this document. The confirmation below is yours to '
                + 'hand over on its own — it names the document, what you concluded, and '
                + 'the checks on the ledger it rests on.'
              : data.reviewed_before
                ? `${data.reviews.length} confirmation${data.reviews.length === 1 ? '' : 's'} `
                  + 'already stand against this document. Yours would be separate from '
                  + 'them, under your own name.'
                : 'Nobody has confirmed reading this document yet. Signing generates an '
                  + 'individual confirmation, with its own reference, under your name.'}
          </p>
        </div>
        {data.yours && <Seal tone={OUTCOME_TONE[data.yours.outcome]}>{data.yours.id}</Seal>}
      </header>

      {/* The other thing this product calls counter-signing. Said here because
          the two are on one page and share the word: a reader who signs this
          and then finds "Who counter-signed it when it was filed" reporting
          something else concludes the signature did not take. */}
      <p className="small rev__vswitness">
        This is not the counter-signature the document was filed with. That one is
        made at capture by an organisation the consortium assigns, it is on the
        ledger, and it is under <strong>Who counter-signed it when it was filed</strong>{' '}
        further down this page. Signing here does not change it and is not meant
        to — the two say different things, and are worth different amounts.
      </p>

      {data.yours ? (
        <Confirmation review={data.yours} yours />
      ) : data.may_confirm ? (
        <div className="rev__form">
          {/* Whose signature this is, before the form rather than after it. The
              person signing should never have to submit to find out. */}
          <p className="rev__who">
            <PenLine size={14} aria-hidden="true" />
            Signing as <strong>{data.you.name}</strong>, {data.you.org}
            <span className="small rev__whorole"> · {data.you.label}</span>
          </p>

          <label className="rev__field">
            <span className="stamp-type">What you concluded</span>
            <select
              className="input"
              value={outcome}
              onChange={(e) => setOutcome(e.target.value as ReviewOutcome)}
            >
              <option value="accepted">Reviewed and accepted</option>
              <option value="qualified">Accepted, with reservations</option>
              <option value="rejected">Not accepted</option>
            </select>
          </label>

          <label className="rev__field">
            <span className="stamp-type">In your own words</span>
            <textarea
              className="input"
              rows={3}
              placeholder="What you examined, and what you concluded…"
              value={statement}
              onChange={(e) => setStatement(e.target.value)}
            />
          </label>

{data.checks_you_ran.length > 0 ? (
            <p className="small rev__rests">
              This will cite {data.checks_you_ran.length} check
              {data.checks_you_ran.length === 1 ? '' : 's'} you have already run against
              this document. Those are on the ledger, and anyone holding the confirmation
              can follow it back to them.
            </p>
          ) : data.may_check ? (
            <p className="small rev__rests">
              You have not checked any row of this document against the ledger yet — the
              check is on each row of the table above, and on the button over it. You can
              sign without doing that, and the confirmation will say plainly that it
              rests on no check, which is a weaker statement and should look like one.
            </p>
          ) : (
            /* No live permission on this document, so there is no check on this
               page and there is no way to put one there from here. Saying "you
               have not checked any row yet" to somebody who cannot check any row
               is the screen blaming them for its own rule. */
            <p className="small rev__rests">
              <strong>There is no check to run on this document.</strong> You can read it
              in full, but proving a figure writes a receipt naming that exact figure, and
              that needs a permission from the factory — nothing here has been released to
              you. Your confirmation will say, in as many words, that it rests on no
              check: it confirms you read the document, not that any figure in it was
              proved.
              {data.you.role === 'auditor' && (
                <> The documents you can prove are in{' '}
                  <Link to="/auditor/workspace">My audit checks</Link>.
                </>
              )}
              {data.you.role === 'buyer' && (
                <> Ask the factory for a figure from{' '}
                  <Link to="/buyer/portal">Request documents</Link>, and the check appears
                  here once it is released.
                </>
              )}
            </p>
          )}

          {failure && <Failed error={failure} />}

          <div className="rev__actions">
            <button
              type="button"
              className="btn btn--primary btn--sm"
              disabled={busy || short}
              onClick={() => void sign()}
            >
              <PenLine size={13} />
              {busy ? 'Signing…' : 'Sign and generate the confirmation'}
            </button>
            {short && (
              <span className="small rev__why">
                {written === 0
                  ? `Write what you concluded first — ${MINIMUM_WORDS} words is enough.`
                  : `${written} word${written === 1 ? '' : 's'} so far; `
                    + `${MINIMUM_WORDS} is the minimum. The confirmation goes to people who `
                    + 'cannot open the document themselves.'}
              </span>
            )}
          </div>
        </div>
      ) : (
        <p className="small rev__none">
          Confirming a review is for the organisations that read this document rather than
          the one that wrote it. What you can see here is who has confirmed it.
        </p>
      )}

      {others.length > 0 && (
        <div className="rev__others">
          <p className="stamp-type rev__othershead">
            {data.yours ? 'Also confirmed by' : 'Confirmed by'}
          </p>
          {others.map((r) => (
            <Confirmation key={r.id} review={r} />
          ))}
        </div>
      )}

    </>
  );
}

/**
 * One confirmation, drawn as the document it is.
 *
 * Including the download, because the whole reason this exists separately from
 * the batch attestation is that somebody has to be able to send it to a party
 * who cannot open the register it is about.
 */
function Confirmation({ review, yours = false }: { review: ReviewConfirmation; yours?: boolean }) {
  return (
    <article className={`revdoc ${yours ? 'is-yours' : ''}`}>
      <header className="revdoc__head">
        <span className="mono revdoc__ref">{review.id}</span>
        <Seal tone={OUTCOME_TONE[review.outcome]}>{OUTCOME_WORD[review.outcome]}</Seal>
      </header>

      <p className="revdoc__by">
        <strong>{review.reviewer_name}</strong>, {review.reviewer_org}
        <span className="small"> · {shortMsp(review.reviewer_msp)}</span>
      </p>
      <p className="small revdoc__when">
        Confirmed {longDate(review.signed_at)} · about document{' '}
        <span className="mono">{review.record_id}</span>
      </p>

      <p className="revdoc__statement">{review.statement}</p>

      <p className="small revdoc__rests">
        {review.checks_cited.length > 0
          ? `Rests on ${review.checks_cited.length} verification receipt`
            + `${review.checks_cited.length === 1 ? '' : 's'} on the ledger: `
            + review.checks_cited.join(', ')
          : 'Rests on no verification receipt. This confirms that the document was read, '
            + 'and not that any figure in it was proved.'}
      </p>

      <div className="revdoc__foot">
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={() => download(review)}
        >
          <Download size={13} /> Download this confirmation
        </button>
        <span className="small revdoc__note">
          <FileText size={11} aria-hidden="true" /> A separate document. Handing it over
          discloses nothing out of the register it is about.
        </span>
      </div>
    </article>
  );
}

/**
 * The confirmation as a file, in plain text.
 *
 * Plain text rather than a rendered PDF on purpose: the value of this document
 * is that every claim in it can be checked against the ledger, and a reader who
 * has to open it in a viewer to do that is being asked for one step too many.
 */
function download(review: ReviewConfirmation) {
  const lines = [
    'BREADCRUMBS — CONFIRMATION OF REVIEW',
    '',
    `Reference       ${review.id}`,
    `Document        ${review.record_id}`,
    `Reviewed by     ${review.reviewer_name}, ${review.reviewer_org}`,
    `Organisation    ${review.reviewer_msp}`,
    `Signed          ${dateTime(review.signed_at)}`,
    `Outcome         ${OUTCOME_WORD[review.outcome]}`,
    '',
    'Statement',
    review.statement,
    '',
    'Evidence on the ledger',
    review.checks_cited.length > 0
      ? review.checks_cited.map((c) => `  receipt ${c}`).join('\n')
      : '  none — this confirms the document was read, not that a figure was proved',
    `  root at the time of review ${review.merkle_root}`,
    '',
    'This confirmation is a professional statement about one document. It is held',
    'off the ledger and can be withdrawn; the verification receipts it cites are on',
    'the ledger and cannot be.',
    '',
  ].join('\n');

  const url = URL.createObjectURL(new Blob([lines], { type: 'text/plain;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `${review.id}-${review.record_id}.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** The tick used where a confirmation is being summarised rather than drawn. */
export function ReviewedMark({ n }: { n: number }) {
  if (n === 0) return null;
  return (
    <span className="revmark small">
      <Check size={11} strokeWidth={3} /> {n} confirmation{n === 1 ? '' : 's'} of review
    </span>
  );
}
