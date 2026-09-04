import { PenLine, Play, RotateCcw } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Failed, Result } from '../components/states';
import { Tech } from '../components/Tech';
import { Field, Seal } from '../components/ui';
import { ApiError, api, recordLabel, shortMsp, type AuditQueue, type QueueItem } from '../lib/api';
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
 * to. So the layout follows that: the queue across the top where work visibly
 * moves left to right, the full table below it, and the signing block along the
 * right in a heavier material than the rest of the page.
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
                  <h1>Checks to run</h1>
                  <p className="lead bench__lede">
                    Each one re-derives a figure's fingerprint and compares it to what the
                    factory published. A pass leaves a receipt the factory can see.
                  </p>
                </div>
                <div className="bench__tally">
                  <Tally n={passed} label="passed" tone="ok" />
                  <Tally n={failed} label="failed" tone="bad" />
                  <Tally n={queued.length} label="not yet run" tone="wait" />
                </div>
              </header>

              {failure && <Failed error={failure} />}

              <section className="rail-strip">
                <div className="rail-strip__head">
                  <p className="stamp-type">The queue</p>
                  <div className="rail-strip__actions">
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
                      {running ? 'Checking…' : `Run all ${queued.length}`}
                    </button>
                  </div>
                </div>

                <ol className="specimens scroll-x">
                  {items.slice(0, 40).map((it) => (
                    <li key={it.grant_id} className={`spec is-${stateOf(it)}`}>
                      <span className="spec__body">
                        <span className="spec__factory">{shortMsp(it.owner_msp)}</span>
                        <span className="small spec__type">{recordLabel(it.record_type)}</span>
                        <Tech><span className="mono spec__id">{it.record_id}</span></Tech>
                      </span>
                      <span className="spec__state stamp-type">{stateOf(it)}</span>
                    </li>
                  ))}
                </ol>
                {items.length > 40 && (
                  <p className="small dim">
                    Showing the first 40 of {commas(items.length)}. The table below has all
                    of them, and Run covers the whole set.
                  </p>
                )}
              </section>

              <div className="bench__body">
                <section className="surface">
                  <div className="scroll-x">
                    <table className="benchtable">
                      <thead>
                        <tr>
                          <th scope="col">Factory</th>
                          <th scope="col">Record</th>
                          <th scope="col">Month</th>
                          <th scope="col">Which figure</th>
                          <Tech><th scope="col">Record id</th></Tech>
                          <th scope="col">Result</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((it) => {
                          const state = stateOf(it);
                          return (
                            <tr key={it.grant_id} className={state === 'failed' ? 'is-fail' : ''}>
                              <th scope="row">{shortMsp(it.owner_msp)}</th>
                              <td>{recordLabel(it.record_type)}</td>
                              <td className="mono">{period(it.period)}</td>
                              <td>{labelOf(it.record_type, it.field_name)}</td>
                              <Tech>
                                <td className="mono dim">
                                  <Link to={`/factory/records/${encodeURIComponent(it.record_id)}`}>
                                    {it.record_id}
                                  </Link>
                                </td>
                              </Tech>
                              <td>
                                <Seal
                                  tone={
                                    state === 'passed' ? 'sealed'
                                      : state === 'failed' ? 'broken'
                                        : state === 'checking' ? 'pending' : 'inert'
                                  }
                                >
                                  {state}
                                </Seal>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>

                <Signing
                  allRun={allRun}
                  queued={queued.length}
                  existing={data.attestations}
                  onSigned={queue.reload}
                />
              </div>
            </>
          );
        }}
      </Result>
    </div>
  );
}

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
      <p className="stamp-type signing__head">Attestation</p>

      {signed ? (
        <div className="wax">
          <div className="wax__seal" aria-hidden="true"><PenLine size={22} /></div>
          <h3 className="wax__head">Signed and submitted.</h3>
          <p className="small wax__body">
            What you sign is recorded against your certificate, and against the checks it
            rests on are on the ledger. It cannot be quietly amended later.
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
          <Field label="Claim code" id="claim">
            <input
              id="claim" className="input mono" value={claim}
              onChange={(e) => setClaim(e.target.value)}
            />
          </Field>
          <Field label="Evidence scope" id="scope">
            <select id="scope" className="input" value={scope} onChange={(e) => setScope(e.target.value)}>
              <option>All records in this batch</option>
              <option>Passed records only</option>
              <option>Selected records</option>
            </select>
          </Field>
          <Field label="Findings, in plain language" id="stmt">
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
              ? `${queued} check${queued === 1 ? '' : 's'} still to run. You cannot sign off on a record that has not been checked. The API refuses it.`
              : statement.trim().length < 12
                ? 'Write your findings before signing.'
                : 'This will be recorded against your certificate.'}
          </p>
        </>
      )}

      {existing.length > 0 && (
        <div className="signing__past">
          <p className="stamp-type">Previously signed</p>
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

function Tally({ n, label, tone }: { n: number; label: string; tone: 'ok' | 'bad' | 'wait' }) {
  return (
    <div className={`tally tally--${tone}`}>
      <span className="tally__n">{n}</span>
      <span className="stamp-type tally__l">{label}</span>
    </div>
  );
}
