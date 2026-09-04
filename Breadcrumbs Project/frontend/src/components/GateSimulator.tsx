import { useEffect, useRef, useState } from 'react';


import { api, taskLabel, type GateDecision } from '../lib/api';
import { bp, bpDelta } from '../lib/format';
import { plainReason } from '../lib/plainReason';
import { useApi } from '../lib/useApi';
import { useReducedMotion } from '../lib/useMotionPref';
import { Seal } from './ui';
import './gate.css';

type Phase = 'idle' | 'running' | 'promote' | 'reject';

/**
 * The seven checks `evaluate_gate` performs, in the order it performs them.
 *
 * They are steps of the algorithm rather than fields of a decision, so they live
 * beside the animation that draws them. The jam always falls on the last one,
 * because the backwards-looking check is the one this whole mechanism exists for.
 */
const GATE_STEPS = [
  'Check the tests are the ones that were published',
  'Collect the signed results from each member',
  'Check enough members took part',
  'Check the members agree with each other',
  'Take the middle result for each problem',
  'Check it is better at the new problem',
  'Check it is not worse at the old ones',
];

/**
 * The Continuity Gate, as a lock.
 *
 * Seven tumblers must align for the gate to open. Six align and one jams when a
 * candidate has forgotten something the network already knew — which is the
 * whole mechanism, made physical.
 *
 * The same object appears on the landing page and on the decision screen, so
 * the marketing surface and the product share a vocabulary rather than merely a
 * palette.
 */
export function GateSimulator({
  decision, compact = false,
}: { decision?: GateDecision; compact?: boolean }) {
  const reduced = useReducedMotion();
  // The two candidates the buttons submit are real decisions off the model
  // channel, fetched from the public explainer endpoint so this works signed out.
  const about = useApi(
    () => (decision ? Promise.resolve(null) : api.about().then((a) => a.gate)),
    [decision],
  );
  const [phase, setPhase] = useState<Phase>('idle');
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<GateDecision | null>(decision ?? null);
  const timers = useRef<number[]>([]);

  useEffect(() => () => timers.current.forEach(window.clearTimeout), []);

  const run = (target: GateDecision) => {
    timers.current.forEach(window.clearTimeout);
    timers.current = [];
    setResult(target);

    if (reduced) {
      setStep(GATE_STEPS.length);
      setPhase(target.outcome);
      return;
    }

    setPhase('running');
    setStep(0);
    // The jam happens on the last tumbler — the backwards-looking check.
    const stops = target.outcome === 'reject' ? GATE_STEPS.length - 1 : GATE_STEPS.length;
    for (let i = 1; i <= stops; i += 1) {
      timers.current.push(window.setTimeout(() => setStep(i), i * 280));
    }
    timers.current.push(
      window.setTimeout(() => setPhase(target.outcome), stops * 280 + 380),
    );
  };

  const shown = result;
  const settled = phase === 'promote' || phase === 'reject';
  const jammedAt = phase === 'reject' ? GATE_STEPS.length - 1 : -1;

  return (
    <div className={`gate ${compact ? 'gate--compact' : ''} is-${phase}`}>
      <div className="gate__mech">
        <div className="gate__shaft" aria-hidden="true">
          {GATE_STEPS.map((_, i) => {
            const done = i < step;
            const jammed = settled && phase === 'reject' && i === jammedAt;
            return (
              <span
                key={i}
                className={`tumbler ${done ? 'is-set' : ''} ${jammed ? 'is-jammed' : ''}`}
                style={{ transitionDelay: `${i * 20}ms` }}
              >
                <span className="tumbler__pin" />
              </span>
            );
          })}
        </div>
        <p className="stamp-type gate__mech-label">
          {phase === 'idle' && 'seven checks'}
          {phase === 'running' && GATE_STEPS[Math.min(step, GATE_STEPS.length - 1)]}
          {phase === 'promote' && 'all seven aligned'}
          {phase === 'reject' && 'one tumbler jammed'}
        </p>
      </div>

      <div className="gate__panel">
        {phase === 'idle' && !decision && (
          <>
            <p className="lead on-dark-muted gate__prompt">
              Submit a model update and watch the contract decide. One of these has
              quietly forgotten something the network already knew.
            </p>
            <div className="gate__actions">
              <button
                type="button"
                className="btn btn--primary btn--md"
                disabled={!about.data?.promoted}
                onClick={() => about.data?.promoted && run(about.data.promoted)}
              >
                Submit a good update
              </button>
              <button
                type="button"
                className="btn btn--onDark btn--md"
                disabled={!about.data?.rejected}
                onClick={() => about.data?.rejected && run(about.data.rejected)}
              >
                Submit a forgetful update
              </button>
            </div>
            {about.error && (
              <p className="small on-dark-muted">
                The gate decisions live on the model channel and the API is not
                answering, so there is nothing real to replay here.
              </p>
            )}
          </>
        )}

        {phase === 'running' && (
          <ol className="gate__steps" aria-live="polite">
            {GATE_STEPS.map((s, i) => (
              <li key={s} className={i < step ? 'is-done' : i === step ? 'is-active' : ''}>
                <span className="mono gate__step-n">{String(i + 1).padStart(2, '0')}</span>
                {s}
              </li>
            ))}
          </ol>
        )}

        {settled && shown && (
          <div className={`outcome outcome--${phase}`} aria-live="polite">
            <Seal tone={phase === 'promote' ? 'sealed' : 'broken'} dark>
              {phase === 'promote' ? 'Approved' : 'Refused'}
            </Seal>
            <h3 className="outcome__head">
              {phase === 'promote'
                ? 'Nothing was forgotten.'
                : 'It forgot something it already knew.'}
            </h3>
            <p className="outcome__reason">{plainReason(shown.reason)}</p>

            <table className="gate__table">
              <thead>
                <tr>
                  <th scope="col">Task</th>
                  <th scope="col">Before</th>
                  <th scope="col">After</th>
                  <th scope="col">Change</th>
                </tr>
              </thead>
              <tbody>
                {shown.per_task.map((t) => (
                  <tr key={t.task_id} className={t.pass ? '' : 'is-fail'}>
                    <th scope="row">
                      {taskLabel(t.task_id)}
                      {t.is_new_task && <span className="gate__new stamp-type">new</span>}
                    </th>
                    <td className="mono">{bp(t.previous_bp)}%</td>
                    <td className="mono">{bp(t.candidate_bp)}%</td>
                    <td className={`mono ${t.pass ? 'ok' : 'bad'}`}>{bpDelta(t.change_bp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {phase === 'reject' && (
              <p className="outcome__closer">
                The contract refused it. No single participant, including whoever runs
                the server, could overrule that.
              </p>
            )}

            {!decision && (
              <button
                type="button"
                className="btn btn--ghost btn--sm gate__again"
                onClick={() => {
                  setPhase('idle');
                  setStep(0);
                }}
              >
                Try the other one
              </button>
            )}

            {decision && (
              <button
                type="button"
                className="btn btn--onDark btn--sm gate__again"
                onClick={() => run(decision)}
              >
                ▷ Replay this decision
              </button>
            )}
          </div>
        )}

        {phase === 'idle' && decision && (
          <button type="button" className="btn btn--primary btn--md" onClick={() => run(decision)}>
            ▷ Replay this decision
          </button>
        )}
      </div>
    </div>
  );
}
