import { PenLine, Play, Upload } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Field, Seal } from '../components/ui';
import { QUEUE, type QueueItem } from '../lib/data';
import { useReducedMotion } from '../lib/useMotionPref';
import './bench.css';

/**
 * The Bench — Meera's workspace.
 *
 * Batch work, in sequence, ending in a signature she puts her professional name
 * to. So the layout is a laboratory bench: a specimen rail across the top where
 * work visibly moves left to right, a dense working surface below, and a signing
 * block along the right in a heavier material than the rest of the page.
 *
 * The signing block stays disabled until every specimen has run, and says why.
 */
export default function AuditorBench() {
  const reduced = useReducedMotion();
  const [items, setItems] = useState<QueueItem[]>(QUEUE);
  const [running, setRunning] = useState(false);
  const [statement, setStatement] = useState('');
  const [signed, setSigned] = useState(false);
  const timers = useRef<number[]>([]);

  useEffect(() => () => timers.current.forEach(window.clearTimeout), []);

  const queued = items.filter((i) => i.state === 'queued');
  const passed = items.filter((i) => i.state === 'passed').length;
  const failed = items.filter((i) => i.state === 'failed').length;
  const allRun = queued.length === 0 && !running;

  const runBatch = () => {
    if (!queued.length) return;
    setRunning(true);
    const targets = queued.map((q) => q.id);

    const settle = (id: string, i: number) => {
      // One specimen fails, because a batch that has only ever been designed
      // passing teaches an auditor nothing about what failure looks like.
      const outcome: QueueItem['state'] = id === 'q5' ? 'failed' : 'passed';
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, state: 'checking' } : it)));
      timers.current.push(
        window.setTimeout(
          () => setItems((prev) => prev.map((it) => (it.id === id ? { ...it, state: outcome } : it))),
          reduced ? 0 : 420,
        ),
      );
      if (i === targets.length - 1) {
        timers.current.push(window.setTimeout(() => setRunning(false), reduced ? 10 : 900));
      }
    };

    targets.forEach((id, i) =>
      timers.current.push(window.setTimeout(() => settle(id, i), reduced ? 0 : i * 400)),
    );
  };

  return (
    <div className="bench">
      <header className="bench__head">
        <div>
          <p className="stamp-type bench__eyebrow">BV Certification · batch of {items.length}</p>
          <h1>The bench</h1>
        </div>
        <div className="bench__tally">
          <Tally n={passed} label="passed" tone="ok" />
          <Tally n={failed} label="failed" tone="bad" />
          <Tally n={queued.length} label="queued" tone="wait" />
        </div>
      </header>

      {/* -- the specimen rail ------------------------------------------- */}
      <section className="rail-strip">
        <div className="rail-strip__head">
          <p className="stamp-type">Specimen rail</p>
          <div className="rail-strip__actions">
            <button type="button" className="btn btn--secondary btn--sm">
              <Upload size={13} /> Add claims CSV
            </button>
            <button
              type="button"
              className="btn btn--primary btn--sm"
              onClick={runBatch}
              disabled={!queued.length || running}
            >
              <Play size={13} /> Run {queued.length} queued
            </button>
          </div>
        </div>

        <ol className="specimens scroll-x">
          {items.map((it) => (
            <li key={it.id} className={`spec is-${it.state}`}>
              <span className="spec__body">
                <span className="spec__factory">{it.factory}</span>
                <span className="small spec__type">{it.recordType}</span>
                <span className="mono spec__id">{it.commitmentId}</span>
              </span>
              <span className="spec__state stamp-type">{it.state}</span>
            </li>
          ))}
        </ol>
      </section>

      {/* -- the working surface ----------------------------------------- */}
      <div className="bench__body">
        <section className="surface">
          <table className="benchtable">
            <thead>
              <tr>
                <th scope="col">Factory</th>
                <th scope="col">Record</th>
                <th scope="col">Period</th>
                <th scope="col">Commitment</th>
                <th scope="col">Result</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id} className={it.state === 'failed' ? 'is-fail' : ''}>
                  <th scope="row">{it.factory}</th>
                  <td>{it.recordType}</td>
                  <td className="mono">{it.period}</td>
                  <td className="mono dim">{it.commitmentId}</td>
                  <td>
                    <Seal
                      tone={
                        it.state === 'passed' ? 'sealed'
                          : it.state === 'failed' ? 'broken'
                            : it.state === 'checking' ? 'pending' : 'inert'
                      }
                    >
                      {it.state}
                    </Seal>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* -- the signing block: a different material --------------------- */}
        <aside className={`signing grain ${signed ? 'is-signed' : ''}`}>
          <p className="stamp-type signing__head">Attestation</p>

          {signed ? (
            <div className="wax">
              <div className="wax__seal" aria-hidden="true">
                <PenLine size={22} />
              </div>
              <h3 className="wax__head">Signed and submitted.</h3>
              <p className="small wax__body">
                Your attestation is on the ledger, bound to this batch and to your
                certificate. It cannot be quietly amended later.
              </p>
              <button
                type="button"
                className="btn btn--onDark btn--sm"
                onClick={() => { setSigned(false); setStatement(''); setItems(QUEUE); }}
              >
                Start another batch
              </button>
            </div>
          ) : (
            <>
              <Field label="Claim code" id="claim">
                <input id="claim" className="input mono" defaultValue="ISO45001-PASS-Q3-2026" />
              </Field>
              <Field label="Evidence scope" id="scope">
                <select id="scope" className="input">
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

              <button
                type="button"
                className="btn btn--primary btn--md btn--full"
                disabled={!allRun || statement.trim().length < 12}
                onClick={() => setSigned(true)}
              >
                <PenLine size={15} /> Sign &amp; submit
              </button>
              <p className="small signing__why">
                {!allRun
                  ? `${queued.length} specimen${queued.length === 1 ? '' : 's'} still to run. You cannot attest to a batch you have not finished.`
                  : statement.trim().length < 12
                    ? 'Write your findings before signing.'
                    : 'This will be recorded against your certificate.'}
              </p>
            </>
          )}
        </aside>
      </div>
    </div>
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
