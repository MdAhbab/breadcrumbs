import { PenLine, Play, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Failed, Result } from '../components/states';
import { Tech } from '../components/Tech';
import { Field, Seal } from '../components/ui';
import { OUTCOME_WORD } from '../components/ReviewSignoff';
import {
  ApiError, api, recordLabel, shortMsp,
  type AuditQueue, type QueueItem, type ReviewConfirmation,
} from '../lib/api';
import { commas, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import { useFieldLabel } from '../lib/useFieldLabel';
import './bench.css';

// Deliberately allows undefined: an entry only exists once this session has
// touched that grant, and everything else falls through to the state the ledger
// reported. Without the undefined the `??` below is dead code to the compiler.
type Running = Record<string, 'checking' | 'passed' | 'failed' | undefined>;

/**
 * The auditor's workspace.
 *
 * Batch work, in sequence, ending in a signature a professional puts their name
 * to. So the layout follows that: one table of checks with the Run button over
 * it, and the signing block along the right in a heavier material.
 *
 * "Run" runs. Each check is a real disclosure proved against the fingerprint on
 * the chain, and each success writes a receipt the factory can see. The
 * previous version moved the states around on a timer and forced one row to
 * fail so the screen had some red in it — which meant the one control on this
 * page that claimed to do work did none, and the failure it showed was
 * decoration.
 */
export default function AuditorBench() {
  const { role } = useSession();
  const queue = useApi(() => api.auditQueue(), []);
  const labelOf = useFieldLabel();
  const [live, setLive] = useState<Running>({});
  const [running, setRunning] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const stateOf = (item: QueueItem) => live[item.grant_id] ?? item.state;

  const runBatch = async (items: QueueItem[]) => {
    const targets = items.filter((i) => stateOf(i) === 'queued');
    if (!targets.length) return;
    setRunning(true);
    setFailure(null);

    for (const item of targets) {
      setLive((s) => ({ ...s, [item.grant_id]: 'checking' }));
      try {
        const proof = await api.proveRow({
          grant_id: item.grant_id,
          record_id: item.record_id,
          row_index: 0,
          field_name: item.field_name,
          receipt_id: `vr-${item.grant_id}-${Date.now().toString(36)}`,
        });
        setLive((s) => ({ ...s, [item.grant_id]: proof.verified ? 'passed' : 'failed' }));
      } catch (err) {
        // A refusal is a result: a revoked grant or a field outside its scope
        // is exactly what an auditor needs to see, with the contract's sentence.
        setLive((s) => ({ ...s, [item.grant_id]: 'failed' }));
        if (err instanceof ApiError) setFailure(err);
      }
    }

    setRunning(false);
    queue.reload();
  };

  return (
    <div className="bench">
      <Result query={queue} pendingLabel="Collecting your batch">
        {(data: AuditQueue) => {
          const items = data.items;
          const queued = items.filter((i) => stateOf(i) === 'queued');
          const passed = items.filter((i) => stateOf(i) === 'passed').length;
          const failed = items.filter((i) => stateOf(i) === 'failed').length;
          const allRun = queued.length === 0 && !running;

          return (
            <>
              <header className="bench__head">
                <div>
                  <p className="stamp-type bench__eyebrow">
                    {role?.org} · {commas(items.length)} to check
                  </p>
                  <h1>My audit checks</h1>
                  <p className="lead bench__lede">
                    Run each check against the ledger, then sign off. Each check leaves a
                    receipt the factory can see.
                  </p>
                </div>
                <div className="bench__tally">
                  <Tally n={passed} label="passed" tone="ok" />
                  <Tally n={failed} label="failed" tone="bad" />
                  <Tally n={queued.length} label="not run" tone="wait" />
                </div>
              </header>

              {failure && <Failed error={failure} />}

              <div className="bench__body">
                <section className="surface">
                  <div className="bench__bar">
                    <button
                      type="button"
                      className="btn btn--secondary btn--sm"
                      onClick={() => { setLive({}); queue.reload(); }}
                      disabled={running}
                    >
                      <RotateCcw size={13} /> Reload from the ledger
                    </button>
                    <button
                      type="button"
                      className="btn btn--primary btn--sm"
                      onClick={() => void runBatch(items)}
                      disabled={!queued.length || running}
                    >
                      <Play size={13} />
                      {running ? 'Checking…' : `Run all ${commas(queued.length)}`}
                    </button>
                  </div>
                  <div className="scroll-x">
                    <table className="benchtable">
                      <thead>
                        <tr>
                          <th scope="col">Factory</th>
                          <th scope="col">Document</th>
                          <th scope="col">Month</th>
                          <th scope="col">Which figure</th>
                          <Tech><th scope="col">Document id</th></Tech>
                          <th scope="col">Result</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((it) => {
                          const state = stateOf(it);
                          return (
                            <tr key={it.grant_id} className={state === 'failed' ? 'is-fail' : ''}>
                              <th scope="row">{shortMsp(it.owner_msp)}</th>
                              <td>
                                <Link to={`/factory/records/${encodeURIComponent(it.record_id)}`}>
                                  {recordLabel(it.record_type)}
                                </Link>
                              </td>
                              <td>{period(it.period)}</td>
                              <td>{labelOf(it.record_type, it.field_name)}</td>
                              <Tech>
                                <td className="mono dim">{it.record_id}</td>
                              </Tech>
                              <td>
                                <Seal
                                  tone={
                                    state === 'passed' ? 'sealed'
                                      : state === 'failed' ? 'broken'
                                        : state === 'checking' ? 'pending' : 'inert'
                                  }
                                >
                                  {STATE_WORD[state]}
                                </Seal>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>

                <div className="bench__aside">
                  <Signing
                    allRun={allRun}
                    queued={queued.length}
                    existing={data.attestations}
                    onSigned={queue.reload}
                  />
                  <Confirmations />
                </div>
              </div>
            </>
          );
        }}
      </Result>
    </div>
  );
}

const STATE_WORD: Record<QueueItem['state'] | 'checking', string> = {
  queued: 'Not run',
  checking: 'Checking…',
  passed: 'Passed',
  failed: 'Failed',
  revoked: 'Withdrawn',
};

/**
 * The signing block, in a different material from the rest of the page.
 *
 * The API refuses an attestation over a batch that still has unverified records
 * — it counts receipts on the chain rather than believing this form — so the
 * disabled state here is a courtesy, not the control.
 */
function Signing({
  allRun, queued, existing, onSigned,
}: {
  allRun: boolean;
  queued: number;
  existing: AuditQueue['attestations'];
  onSigned: () => void;
}) {
  const [claim, setClaim] = useState('ISO45001-PASS-2027');
  const [scope, setScope] = useState('All records in this batch');
  const [statement, setStatement] = useState('');
  const [signed, setSigned] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const submit = async () => {
    setBusy(true);
    setFailure(null);
    try {
      await api.attest({ claim_code: claim, evidence_scope: scope, statement });
      setSigned(true);
      onSigned();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'signing off failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className={`signing grain ${signed ? 'is-signed' : ''}`}>
      <p className="stamp-type signing__head">Sign off</p>

      {signed ? (
        <div className="wax">
          <div className="wax__seal" aria-hidden="true"><PenLine size={22} /></div>
          <h3 className="wax__head">Signed and submitted.</h3>
          <p className="small wax__body">
            It is saved on the ledger with the checks it rests on. It cannot be changed later.
          </p>
          <button
            type="button"
            className="btn btn--onDark btn--sm"
            onClick={() => { setSigned(false); setStatement(''); }}
          >
            Write another
          </button>
        </div>
      ) : (
        <>
          <Field label="Certificate code" id="claim">
            <input
              id="claim" className="input mono" value={claim}
              onChange={(e) => setClaim(e.target.value)}
            />
          </Field>
          {/* The values are what the API stores, so only the labels are reworded. */}
          <Field label="Which documents" id="scope">
            <select id="scope" className="input" value={scope} onChange={(e) => setScope(e.target.value)}>
              <option value="All records in this batch">All documents in this batch</option>
              <option value="Passed records only">Only documents that passed</option>
              <option value="Selected records">Selected documents</option>
            </select>
          </Field>
          <Field label="Your findings" id="stmt">
            <textarea
              id="stmt"
              className="input"
              rows={5}
              placeholder="What you examined, and what you concluded…"
              value={statement}
              onChange={(e) => setStatement(e.target.value)}
            />
          </Field>

          {failure && <Failed error={failure} />}

          <button
            type="button"
            className="btn btn--primary btn--md btn--full"
            disabled={busy || !allRun || statement.trim().length < 12}
            onClick={() => void submit()}
          >
            <PenLine size={15} /> {busy ? 'Signing…' : 'Sign off'}
          </button>
          <p className="small signing__why">
            {!allRun
              ? `Run the last ${commas(queued)} check${queued === 1 ? '' : 's'} first.`
              : statement.trim().length < 12
                ? 'Write your findings before signing.'
                : 'This is saved against your certificate code.'}
          </p>
        </>
      )}

      {existing.length > 0 && (
        <div className="signing__past">
          <p className="stamp-type">Signed before</p>
          <ul>
            {existing.map((a) => (
              <li key={a.id}>
                <span className="mono">{a.claim_code}</span>
                <span className="small"> · {longDate(a.signed_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

/**
 * The individual confirmations this auditor has signed, as against the batch.
 *
 * An attestation covers everything examined in a sitting and names no document,
 * which is the right shape for a certification decision and the wrong one for
 * the question a factory actually asks: has anybody looked at *this* register.
 * Each of these is one document, signed once, with its own reference and the
 * receipts it rests on named inside it — they are signed from the document
 * itself, and collected here so they can be found again.
 */
function Confirmations() {
  const mine = useApi(() => api.reviews(), []);
  const rows: ReviewConfirmation[] = mine.data ?? [];

  return (
    <aside className="confirms">
      <p className="stamp-type confirms__head">Confirmations of review</p>
      {rows.length === 0 ? (
        <p className="small confirms__none">
          None yet. Sign one at the foot of any document.
        </p>
      ) : (
        <>
          <ul className="confirms__list">
            {rows.slice(0, 8).map((r) => (
              <li key={r.id} className="confirms__row">
                <Link
                  to={`/factory/records/${encodeURIComponent(r.record_id)}`}
                  className="mono confirms__doc"
                >
                  {r.record_id}
                </Link>
                <span className="small confirms__meta">
                  {r.id} · {OUTCOME_WORD[r.outcome]} · {longDate(r.signed_at)} ·{' '}
                  {r.checks_cited.length === 1 ? '1 check' : `${commas(r.checks_cited.length)} checks`}
                </span>
              </li>
            ))}
          </ul>
          {rows.length > 8 && (
            <p className="small confirms__none">Showing 8 of {commas(rows.length)}.</p>
          )}
        </>
      )}
    </aside>
  );
}

function Tally({ n, label, tone }: { n: number; label: string; tone: 'ok' | 'bad' | 'wait' }) {
  return (
    <div className={`tally tally--${tone}`}>
      <span className="tally__n">{n}</span>
      <span className="stamp-type tally__l">{label}</span>
    </div>
  );
}
