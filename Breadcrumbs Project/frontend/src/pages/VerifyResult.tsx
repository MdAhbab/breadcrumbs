import { ArrowLeft, Check, X } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { Failed, Result } from '../components/states';
import { Disclosure, Field, HashChip, LedgerRow, Seal } from '../components/ui';
import {
  ApiError, api, recordLabel, shortMsp,
  type Grant, type PublicReceipt, type RowProof,
} from '../lib/api';
import { commas, dateTime, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
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
    ? { to: role.landing, label: role.instrument }
    : { to: '/', label: 'Breadcrumbs' };
}

/* -- the public path ------------------------------------------------------ */
function FromReceipt({ id }: { id: string }) {
  const query = useApi(() => api.receipt(id), [id]);
  const back = useWayBack();

  return (
    <div className="lb">
      <header className="lb__bar">
        <Link to={back.to} className="lb__back"><ArrowLeft size={15} /> {back.label}</Link>
        <Link to="/verify" className="lb__toggle small">verify something else</Link>
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
                        ? 'Verified — the record is genuine.'
                        : 'Proof failed — do not rely on this record.'}
                    </h1>
                    <p className="lead verdictbar__body">
                      {ok ? (
                        <>
                          This disclosure was proved against the root{' '}
                          {data.record ? shortMsp(data.record.owner_msp) : 'the owner'} sealed
                          on {data.record ? longDate(data.record.committed_at) : 'the ledger'}.
                          The record has not changed since.
                        </>
                      ) : (
                        <>
                          The root recorded on this receipt does not match what is committed
                          on the ledger. Either the record or the receipt has been altered.
                          Ask for it to be re-issued, and do not treat it as evidence.
                        </>
                      )}
                    </p>
                  </div>
                </div>

                <section className="specimen">
                  <p className="stamp-type specimen__field">{data.receipt.field_name}</p>
                  <p className="specimen__value specimen__value--withheld">disclosed privately</p>
                  <div className="specimen__seal">
                    <Seal tone={ok ? 'sealed' : 'broken'}>{ok ? 'Verified' : 'Proof failed'}</Seal>
                  </div>
                  <p className="specimen__note small">{data.note}</p>
                </section>

                <div className="lb__detail">
                  <Disclosure summary="How this was checked" open>
                    <p className="small lb__explain">
                      The owner disclosed one row, the salt it was hashed with, and the
                      sibling hashes on that row&rsquo;s path to the root. The verifier
                      recomputed the root from those alone. This page compares the root
                      the receipt recorded against the one on the ledger now.
                    </p>

                    <div className={`proof ${ok ? '' : 'is-bad'}`}>
                      <div className="proof__side">
                        <p className="stamp-type">Root recorded on the receipt</p>
                        <p className="mono proof__hash">{data.receipt.computed_root}</p>
                      </div>
                      <div className="proof__verdict">
                        <span className={`proof__badge stamp-type ${ok ? 'ok' : 'bad'}`}>
                          {data.root_matches ? 'match' : 'no match'}
                        </span>
                      </div>
                      <div className="proof__side">
                        <p className="stamp-type">On the ledger</p>
                        <p className="mono proof__hash">{data.on_chain_root ?? 'no such record'}</p>
                      </div>
                    </div>
                  </Disclosure>

                  <Disclosure summary="Verification receipt">
                    <div className="receipt">
                      <LedgerRow label="Receipt">
                        <span className="mono">{data.receipt.receipt_id}</span>
                      </LedgerRow>
                      <LedgerRow label="Verifier">{shortMsp(data.receipt.verifier_msp)}</LedgerRow>
                      <LedgerRow label="Field verified">
                        <span className="mono">{data.receipt.field_name}</span>
                      </LedgerRow>
                      <LedgerRow label="Verified at">{dateTime(data.receipt.verified_at)}</LedgerRow>
                      <LedgerRow label="Result">
                        {data.receipt.result === 'match'
                          ? 'Match — the record is genuine'
                          : 'No match — proof failed'}
                      </LedgerRow>
                      {data.record && (
                        <>
                          <LedgerRow label="Record">
                            <span className="mono">{data.record.record_id}</span>
                          </LedgerRow>
                          <LedgerRow label="Document">
                            {recordLabel(data.record.record_type)} · {period(data.record.period)} ·{' '}
                            {data.record.site}
                          </LedgerRow>
                          <LedgerRow label="Rows in the record">
                            {commas(data.record.row_count)} — one was disclosed
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
function LiveProof({ signedIn }: { signedIn: boolean }) {
  const grants = useApi(
    () => (signedIn ? api.grants() : Promise.resolve([] as Grant[])),
    [signedIn],
  );
  const [picked, setPicked] = useState('');
  const [row, setRow] = useState(0);
  const [field, setField] = useState('');
  const [proof, setProof] = useState<RowProof | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const back = useWayBack();

  const live = (grants.data ?? []).filter((g) => g.status === 'active');
  const grant = live.find((g) => g.grant_id === picked) ?? live[0];

  const run = async () => {
    if (!grant) return;
    setBusy(true);
    setFailure(null);
    setProof(null);
    try {
      setProof(await api.proveRow({
        grant_id: grant.grant_id,
        record_id: grant.record_id,
        row_index: row,
        field_name: field.trim() || grant.field_name,
        receipt_id: `vr-live-${Date.now().toString(36)}`,
      }));
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'the proof failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="lb">
      <header className="lb__bar">
        <Link to={back.to} className="lb__back"><ArrowLeft size={15} /> {back.label}</Link>
      </header>

      <main className="lb__main">
        <div className="verdictbar">
          <div>
            <h1 className="verdictbar__head">Prove one value.</h1>
            <p className="lead verdictbar__body">
              Pick a grant you hold and a row. The factory discloses that single field
              with its salt and the sibling hashes on its path; the root is recomputed
              from those alone and compared to what is on the ledger.
            </p>
          </div>
        </div>

        {!signedIn ? (
          <section className="specimen">
            <p className="specimen__note">
              Running a live proof needs a grant, and a grant belongs to an organisation.
              If you were given a receipt identifier you can check it without signing in.
            </p>
            <div className="lb__after-actions">
              <Link to="/login" className="btn btn--primary btn--md">Sign in</Link>
            </div>
          </section>
        ) : (
          <Result query={grants} pendingLabel="Reading the grants you hold">
            {() => (
              <section className="lb__detail">
                {live.length === 0 ? (
                  <p className="small lb__explain">
                    You hold no live grant, so there is nothing you may disclose. Ask for
                    one from the portal.
                  </p>
                ) : (
                  <>
                    <Field label="Grant" id="grant">
                      <select
                        id="grant"
                        className="input"
                        value={grant?.grant_id ?? ''}
                        onChange={(e) => { setPicked(e.target.value); setProof(null); }}
                      >
                        {live.slice(0, 60).map((g) => (
                          <option key={g.grant_id} value={g.grant_id}>
                            {g.record_id} · {g.field_name} · {g.purpose_code}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Row index" id="row" hint="Zero-based.">
                      <input
                        id="row" className="input mono" type="number" min={0} value={row}
                        onChange={(e) => setRow(Number(e.target.value))}
                      />
                    </Field>
                    <Field
                      label="Field"
                      id="fieldname"
                      hint={`Leave blank to use the granted field, ${grant?.field_name ?? ''}. Naming another is refused by the contract — try it.`}
                    >
                      <input
                        id="fieldname" className="input mono" value={field}
                        placeholder={grant?.field_name}
                        onChange={(e) => setField(e.target.value)}
                      />
                    </Field>

                    <button
                      type="button"
                      className="btn btn--primary btn--md"
                      onClick={() => void run()}
                      disabled={busy}
                    >
                      {busy ? 'Proving…' : 'Run the proof'}
                    </button>

                    {failure && <Failed error={failure} />}

                    {proof && <ProofResult proof={proof} />}
                  </>
                )}
              </section>
            )}
          </Result>
        )}

        <div className="lb__detail"><Afterword /></div>
      </main>
    </div>
  );
}

function ProofResult({ proof }: { proof: RowProof }) {
  const ok = proof.verified;
  return (
    <>
      <div className={`verdictbar ${ok ? 'is-ok' : 'is-bad'}`}>
        <span className="verdictbar__mark" aria-hidden="true">
          {ok ? <Check size={20} strokeWidth={2.5} /> : <X size={20} strokeWidth={2.5} />}
        </span>
        <div>
          <h1 className="verdictbar__head">{proof.verdict}</h1>
        </div>
      </div>

      <section className="specimen">
        <p className="stamp-type specimen__field">{proof.disclosed.field_name}</p>
        <p className="specimen__value">{String(proof.disclosed.value)}</p>
        <div className="specimen__seal">
          <Seal tone={ok ? 'sealed' : 'broken'}>{ok ? 'Verified' : 'Proof failed'}</Seal>
        </div>
        <p className="specimen__note small">
          Only this single value was disclosed. The register holds{' '}
          {commas(proof.proof.rows_in_record)} rows; the other{' '}
          {commas(proof.proof.rows_in_record - 1)} were never transmitted and cannot be
          recovered from what you received.
        </p>
      </section>

      <Disclosure summary="How we checked this" open>
        <div className={`proof ${ok ? '' : 'is-bad'}`}>
          <div className="proof__side">
            <p className="stamp-type">Computed root</p>
            <p className="mono proof__hash">{proof.proof.computed_root}</p>
          </div>
          <div className="proof__verdict">
            <span className={`proof__badge stamp-type ${ok ? 'ok' : 'bad'}`}>
              {proof.proof.match ? 'match' : 'no match'}
            </span>
          </div>
          <div className="proof__side">
            <p className="stamp-type">On the ledger</p>
            <p className="mono proof__hash">{proof.proof.on_chain_root}</p>
          </div>
        </div>

        <Disclosure summary={`Show the ${proof.proof.steps.length} steps`}>
          <ol className="ladder">
            {proof.proof.steps.map((s, i) => (
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
          <LedgerRow label="Receipt"><span className="mono">{proof.receipt.receipt_id}</span></LedgerRow>
          <LedgerRow label="Verifier">{shortMsp(proof.receipt.verifier_msp)}</LedgerRow>
          <LedgerRow label="Verified at">{dateTime(proof.receipt.verified_at)}</LedgerRow>
          <LedgerRow label="Transaction"><HashChip value={proof.tx_id} /></LedgerRow>
          <LedgerRow label="Block"><span className="mono">#{commas(proof.block)}</span></LedgerRow>
          <LedgerRow label="Shareable link">
            <Link to={`/verify/${encodeURIComponent(proof.receipt.receipt_id)}`} className="mono">
              /verify/{proof.receipt.receipt_id}
            </Link>
          </LedgerRow>
        </div>
      </Disclosure>
    </>
  );
}

function Afterword() {
  const { role } = useSession();
  return (
    <footer className="lb__after">
      <p className="lb__after-lede">
        Anyone holding a receipt can run this check. It needs no account, and it asks the
        factory for nothing.
      </p>
      <div className="lb__after-actions">
        {role ? (
          <Link to={role.landing} className="btn btn--primary btn--md">
            Back to {role.instrument}
          </Link>
        ) : (
          <>
            <Link to="/" className="btn btn--primary btn--md">What Breadcrumbs is</Link>
            <Link to="/login" className="btn btn--secondary btn--md">Sign in to the portal</Link>
          </>
        )}
      </div>
    </footer>
  );
}
