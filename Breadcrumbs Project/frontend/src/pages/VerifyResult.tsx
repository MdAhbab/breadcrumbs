import { ArrowLeft, Check, Download, X } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Disclosure, HashChip, LedgerRow, Seal } from '../components/ui';
import { PURPOSE_CODES, VERIFICATION, orgName } from '../lib/data';
import { commas, dateTime, longDate } from '../lib/format';
import './verify.css';

/**
 * The Lightbox — one object on a clean field.
 *
 * This is the product's thesis in one screen, and it is governed by the
 * five-second test: someone who does not know what a hash is must be able to
 * answer "is this genuine?" before they have finished arriving.
 *
 * So the disclosed value is enormous and alone, the verdict is one plain
 * sentence, and every piece of cryptography is collapsed beneath a disclosure.
 * Nothing technical is allowed to compete with the answer.
 */
export default function VerifyResult() {
  const v = VERIFICATION;
  // The failure state is one toggle away, because a verification screen that
  // has only ever been designed passing is not finished.
  const [failed, setFailed] = useState(false);
  const ok = v.verified && !failed;

  return (
    <div className="lb">
      <header className="lb__bar">
        <Link to="/" className="lb__back">
          <ArrowLeft size={15} /> Breadcrumbs
        </Link>
        <button
          type="button"
          className="lb__toggle small"
          onClick={() => setFailed((f) => !f)}
          title="Both outcomes are designed; this switches between them"
        >
          view the {ok ? 'failure' : 'success'} state
        </button>
      </header>

      <main className="lb__main">
        {/* -- the verdict: one plain sentence ------------------------------ */}
        <div className={`verdictbar ${ok ? 'is-ok' : 'is-bad'}`}>
          <span className="verdictbar__mark" aria-hidden="true">
            {ok ? <Check size={20} strokeWidth={2.5} /> : <X size={20} strokeWidth={2.5} />}
          </span>
          <div>
            <h1 className="verdictbar__head">
              {ok ? 'Verified — the record is genuine.' : 'Proof failed — do not rely on this record.'}
            </h1>
            <p className="lead verdictbar__body">
              {ok ? (
                <>
                  This entry matches the record Apex Textile Ltd sealed on{' '}
                  {longDate(v.verifiedAt)}. The value has not changed since.
                </>
              ) : (
                <>
                  The value you were shown does not match what Apex Textile Ltd sealed on{' '}
                  {longDate(v.verifiedAt)}. Either the value or the proof has been altered.
                  Ask the factory to re-issue it, and do not treat this figure as evidence.
                </>
              )}
            </p>
          </div>
        </div>

        {/* -- the specimen: one object, enormous, alone -------------------- */}
        <section className="specimen">
          <p className="stamp-type specimen__field">{v.fieldName}</p>
          <p className="specimen__value">{failed ? '19,940 BDT' : v.value}</p>
          <div className="specimen__seal">
            <Seal tone={ok ? 'sealed' : 'broken'}>{ok ? 'Verified' : 'Proof failed'}</Seal>
          </div>
          <p className="specimen__note small">
            Only this single value was disclosed. The register holds{' '}
            {commas(v.rowsInRecord)} rows; the other {commas(v.rowsInRecord - 1)} were
            never transmitted and cannot be recovered from what you received.
          </p>
        </section>

        {/* -- everything technical, collapsed by default ------------------- */}
        <div className="lb__detail">
          <Disclosure summary="How we checked this" open>
            <p className="small lb__explain">
              The factory disclosed one row, the salt it was hashed with, and the eleven
              sibling hashes on that row&rsquo;s path to the root. We recomputed the root
              from those alone and compared it to the value already on the ledger.
            </p>

            <div className={`proof ${ok ? '' : 'is-bad'}`}>
              <div className="proof__side">
                <p className="stamp-type">Computed root</p>
                <p className="mono proof__hash">
                  {failed ? v.computedRoot.slice(0, 40).replace(/.$/, '9') + '…' : v.computedRoot}
                </p>
              </div>
              <div className="proof__verdict">
                <span className={`proof__badge stamp-type ${ok ? 'ok' : 'bad'}`}>
                  {ok ? 'match' : 'no match'}
                </span>
              </div>
              <div className="proof__side">
                <p className="stamp-type">On the ledger</p>
                <p className="mono proof__hash">{v.onChainRoot}</p>
              </div>
            </div>

            <Disclosure summary={`Show the ${v.steps.length} steps`}>
              <ol className="ladder">
                {v.steps.map((s, i) => (
                  <li key={i} className="ladder__step">
                    <span className="mono ladder__n">{String(i + 1).padStart(2, '0')}</span>
                    <span className="ladder__side stamp-type">{s.position}</span>
                    <HashChip value={s.sibling} />
                  </li>
                ))}
              </ol>
            </Disclosure>
          </Disclosure>

          <Disclosure summary="Verification receipt">
            <div className="receipt">
              <LedgerRow label="Requester">
                James Holloway — {orgName(v.requesterMsp)}
              </LedgerRow>
              <LedgerRow label="Purpose">
                {PURPOSE_CODES[v.purposeCode]}{' '}
                <span className="mono lb__code">{v.purposeCode}</span>
              </LedgerRow>
              <LedgerRow label="Field verified">
                <span className="mono">{v.fieldName}</span>
              </LedgerRow>
              <LedgerRow label="Verified at">{dateTime(v.verifiedAt)}</LedgerRow>
              <LedgerRow label="Result">
                {ok ? 'Match — the record is genuine' : 'No match — proof failed'}
              </LedgerRow>
              <LedgerRow label="Transaction">
                <HashChip value={v.txId} />
              </LedgerRow>
              <LedgerRow label="Block">
                <span className="mono">#{commas(v.block)}</span>
              </LedgerRow>
            </div>
            <button type="button" className="btn btn--secondary btn--sm receipt__dl">
              <Download size={14} /> Download receipt (PDF / JSON)
            </button>
          </Disclosure>

          {/* A verification that ends in nothing leaves the reader stranded on
              the one screen most likely to be their first. */}
          <footer className="lb__after">
            <p className="lb__after-lede">
              Anyone holding a receipt can run this check. It needs no account, and it
              asks the factory for nothing.
            </p>
            <div className="lb__after-actions">
              <Link to="/" className="btn btn--primary btn--md">
                What Breadcrumbs is
              </Link>
              <Link to="/login" className="btn btn--secondary btn--md">
                Sign in to the portal
              </Link>
            </div>
          </footer>
        </div>
      </main>
    </div>
  );
}
