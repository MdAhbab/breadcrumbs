import { ArrowLeft, Check, X } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { DocumentCheck } from '../components/DocumentCheck';
import { Result } from '../components/states';
import { Disclosure, Field, LedgerRow, Seal } from '../components/ui';
import {
  api, recordLabel, shortMsp,
  type Grant, type LedgerRecord, type PublicReceipt,
} from '../lib/api';
import { commas, dateTime, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import { useFieldLabel } from '../lib/useFieldLabel';
import './verify.css';

/**
 * One object on a clean field.
 *
 * This is the product's thesis in one screen, and it is governed by the
 * five-second test: someone who does not know what a hash is must be able to
 * answer "is this genuine?" before they have finished arriving. So the verdict
 * is one plain sentence and every piece of cryptography is collapsed beneath a
 * disclosure. Nothing technical competes with the answer.
 *
 * Two ways in, and they are deliberately not the same:
 *
 *   * With a receipt identifier, and no account. Anyone can check that a
 *     disclosure was proved against the root its owner committed. The *value*
 *     is not shown, because it was released to one counterparty under a grant
 *     covering one field, and republishing it to anyone holding a receipt id
 *     would undo the disclosure model this whole product is about.
 *   * Signed in as the party that holds the grant. Then the proof is run live
 *     and the figure is on screen, because it was disclosed to you.
 *
 * The previous version showed a hardcoded value with a toggle that flipped
 * between a designed success and a designed failure. Both outcomes are still
 * reachable — but now by verifying something that passes and something that
 * does not.
 */
export default function VerifyResult() {
  const { id } = useParams();
  const { role } = useSession();
  return id ? <FromReceipt id={id} /> : <LiveProof signedIn={role !== null} />;
}

/**
 * Where "back" goes.
 *
 * This screen is reachable with an account and without one, and the way out
 * should match the way in. A visitor holding a receipt belongs on the landing
 * page; somebody signed in arrived from their own workspace and expects to be
 * returned to it rather than dropped on the page that explains the product to
 * strangers.
 */
function useWayBack(): { to: string; label: string } {
  const { role } = useSession();
  return role
    ? { to: role.landing, label: role.workspace }
    : { to: '/', label: 'Breadcrumbs' };
}

/* -- the public path ------------------------------------------------------ */
function FromReceipt({ id }: { id: string }) {
  const query = useApi(() => api.receipt(id), [id]);
  const back = useWayBack();
  const labelOf = useFieldLabel();

  return (
    <div className="lb">
      <header className="lb__bar">
        <Link to={back.to} className="lb__back"><ArrowLeft size={15} /> {back.label}</Link>
        <Link to="/verify" className="lb__toggle small">check something else</Link>
      </header>

      <main className="lb__main">
        <Result query={query} pendingLabel="Looking the receipt up on the ledger">
          {(data: PublicReceipt) => {
            const ok = data.root_matches && data.receipt.result === 'match';
            return (
              <>
                <div className={`verdictbar ${ok ? 'is-ok' : 'is-bad'}`}>
                  <span className="verdictbar__mark" aria-hidden="true">
                    {ok ? <Check size={20} strokeWidth={2.5} /> : <X size={20} strokeWidth={2.5} />}
                  </span>
                  <div>
                    <h1 className="verdictbar__head">
                      {ok
                        ? 'Checked. This value is real.'
                        : 'The check failed. Do not rely on this record.'}
                    </h1>
                    <p className="lead verdictbar__body">
                      {ok ? (
                        <>
                          The value was checked against the fingerprint{' '}
                          {data.record ? shortMsp(data.record.owner_msp) : 'the owner'} published
                          on {data.record ? longDate(data.record.committed_at) : 'the ledger'},
                          and it matches. Nothing has been altered since.
                        </>
                      ) : (
                        <>
                          The fingerprint on this receipt is not the one on the ledger.
                          Either the record or the receipt was altered after it was made.
                          Ask for it to be issued again, and do not treat this as evidence.
                        </>
                      )}
                    </p>
                  </div>
                </div>

                <section className="specimen">
                  <p className="stamp-type specimen__field">
                    {labelOf(data.record?.record_type ?? '', data.receipt.field_name)}
                  </p>
                  <p className="specimen__value specimen__value--withheld">disclosed privately</p>
                  <div className="specimen__seal">
                    <Seal tone={ok ? 'sealed' : 'broken'}>{ok ? 'Genuine' : 'Failed'}</Seal>
                  </div>
                  <p className="specimen__note small">{data.note}</p>
                </section>

                <div className="lb__detail">
                  <Disclosure summary="How this was checked" open>
                    <p className="small lb__explain">
                      The factory released one row, the random number it was mixed with,
                      and a handful of numbers from the tree above it. Whoever ran the
                      check worked the fingerprint out again from only those. This page
                      compares the answer they got with what is on the ledger now.
                    </p>

                    <div className={`proof ${ok ? '' : 'is-bad'}`}>
                      <div className="proof__side">
                        <p className="stamp-type">Worked out at the time of the check</p>
                        <p className="mono proof__hash">{data.receipt.computed_root}</p>
                      </div>
                      <div className="proof__verdict">
                        <span className={`proof__badge stamp-type ${ok ? 'ok' : 'bad'}`}>
                          {data.root_matches ? 'identical' : 'different'}
                        </span>
                      </div>
                      <div className="proof__side">
                        <p className="stamp-type">On the ledger now</p>
                        <p className="mono proof__hash">{data.on_chain_root ?? 'no such record'}</p>
                      </div>
                    </div>
                  </Disclosure>

                  <Disclosure summary="The receipt">
                    <div className="receipt">
                      <LedgerRow label="Receipt">
                        <span className="mono">{data.receipt.receipt_id}</span>
                      </LedgerRow>
                      <LedgerRow label="Checked by">{shortMsp(data.receipt.verifier_msp)}</LedgerRow>
                      <LedgerRow label="What was checked">
                        {labelOf(data.record?.record_type ?? '', data.receipt.field_name)}
                      </LedgerRow>
                      <LedgerRow label="Checked at">{dateTime(data.receipt.verified_at)}</LedgerRow>
                      <LedgerRow label="Result">
                        {data.receipt.result === 'match'
                          ? 'They match. The record is real.'
                          : 'They do not match. The check failed.'}
                      </LedgerRow>
                      {data.record && (
                        <>
                          <LedgerRow label="Record">
                            <span className="mono">{data.record.record_id}</span>
                          </LedgerRow>
                          <LedgerRow label="What it is">
                            {recordLabel(data.record.record_type)} · {period(data.record.period)} ·{' '}
                            {data.record.site}
                          </LedgerRow>
                          <LedgerRow label="Rows in the record">
                            {commas(data.record.row_count)}, of which one was released
                          </LedgerRow>
                        </>
                      )}
                      <LedgerRow label="Grant">
                        <span className="mono">{data.receipt.grant_id}</span>
                      </LedgerRow>
                    </div>
                  </Disclosure>

                  <Afterword />
                </div>
              </>
            );
          }}
        </Result>
      </main>
    </div>
  );
}

/* -- the signed-in path --------------------------------------------------- */
/**
 * The signed-in path: a document, and the proof that it is real.
 *
 * This screen used to be a form. It asked for a grant, then a row number, then
 * a column name, and returned one value. That is the shape of the API and not
 * the shape of anybody's question: nobody arrives wanting row 0 of anything.
 * A buyer opens what it was given, reads it, and wants to know whether it is
 * true — so the screen is now the document, with the check on every row of it.
 */
function LiveProof({ signedIn }: { signedIn: boolean }) {
  const back = useWayBack();
  const [params] = useSearchParams();

  // Everything this account can open. For a buyer that is what it holds
  // permissions on; for an auditor it is every document on the network.
  const records = useApi(
    () => (signedIn ? api.records() : Promise.resolve([] as LedgerRecord[])),
    [signedIn],
  );
  const grants = useApi(
    () => (signedIn ? api.grants() : Promise.resolve([] as Grant[])),
    [signedIn],
  );

  const [chosen, setChosen] = useState<string | null>(null);

  if (!signedIn) {
    return (
      <div className="lb">
        <header className="lb__bar">
          <Link to={back.to} className="lb__back"><ArrowLeft size={15} /> {back.label}</Link>
        </header>
        <main className="lb__main">
          <div className="verdictbar">
            <div>
              <h1 className="verdictbar__head">Check a document.</h1>
              <p className="lead verdictbar__body">
                Opening a document needs an account, because what you can see depends on
                who you are. If somebody gave you a receipt link, you can check that one
                without signing in.
              </p>
            </div>
          </div>
          <section className="specimen">
            <div className="lb__after-actions">
              <Link to="/login" className="btn btn--primary btn--md">Sign in</Link>
            </div>
          </section>
          <div className="lb__detail"><Afterword /></div>
        </main>
      </div>
    );
  }

  return (
    <div className="lb">
      <header className="lb__bar">
        <Link to={back.to} className="lb__back"><ArrowLeft size={15} /> {back.label}</Link>
      </header>

      <main className="lb__main lb__main--wide">
        <Result query={records} pendingLabel="Reading what you can open">
          {(all: LedgerRecord[]) => {
            if (all.length === 0) {
              return (
                <div className="verdictbar">
                  <div>
                    <h1 className="verdictbar__head">Nothing to check yet.</h1>
                    <p className="lead verdictbar__body">
                      Nothing has been released to you, so there is no document to open.
                      Ask a factory for something first.
                    </p>
                  </div>
                </div>
              );
            }

            // A record named in the link wins: the reader pressed "check" on a
            // specific document and expects that one.
            const wanted = params.get('record');
            const held = new Set(
              (grants.data ?? []).filter((g) => g.status === 'active').map((g) => g.record_id),
            );
            // Documents something has actually been released from come first,
            // because those are the ones that can be proved as well as read.
            const ordered = [...all].sort(
              (a, b) => Number(held.has(b.record_id)) - Number(held.has(a.record_id)),
            );
            const recordId = chosen
              ?? (wanted && all.some((r) => r.record_id === wanted) ? wanted : null)
              ?? ordered[0].record_id;
            const record = all.find((r) => r.record_id === recordId) ?? ordered[0];

            return (
              <>
                <div className="verdictbar">
                  <div>
                    <h1 className="verdictbar__head">Check a document.</h1>
                    <p className="lead verdictbar__body">
                      Everything you have been allowed to read, laid out as it is in the
                      file. Checking a row works the fingerprint out again from what you
                      were sent and compares it to what the factory published. If they
                      match, the figures are real, and you did not have to take anyone{"’"}s
                      word for it.
                    </p>
                  </div>
                </div>

                <div className="lb__detail">
                  <Field
                    label="Which document"
                    id="doc"
                    hint={`${commas(all.length)} you can open.`}
                  >
                    <select
                      id="doc"
                      className="input"
                      value={record.record_id}
                      onChange={(e) => setChosen(e.target.value)}
                    >
                      {ordered.map((r) => (
                        <option key={r.record_id} value={r.record_id}>
                          {recordLabel(r.record_type)} · {period(r.period)} · {r.site}
                          {held.has(r.record_id) ? '' : ' (read only)'}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <DocumentCheck key={record.record_id} recordId={record.record_id} />
                </div>

                <footer className="lb__after">
                  <p className="lb__after-lede">
                    Every check you run here writes a receipt onto the ledger. The factory
                    can see them, and so can anyone you send the link to, without needing
                    an account or asking the factory for anything.
                  </p>
                  <div className="lb__after-actions">
                    <Link to={back.to} className="btn btn--primary btn--md">
                      Back to {back.label}
                    </Link>
                  </div>
                </footer>
              </>
            );
          }}
        </Result>
      </main>
    </div>
  );
}

function Afterword() {
  const { role } = useSession();
  return (
    <footer className="lb__after">
      <p className="lb__after-lede">
        Anyone with the link can run this check. It needs no account, and it asks the
        factory for nothing.
      </p>
      <div className="lb__after-actions">
        {role ? (
          <Link to={role.landing} className="btn btn--primary btn--md">
            Back to {role.workspace}
          </Link>
        ) : (
          <>
            <Link to="/" className="btn btn--primary btn--md">What Breadcrumbs is</Link>
            <Link to="/login" className="btn btn--secondary btn--md">Sign in</Link>
          </>
        )}
      </div>
    </footer>
  );
}
