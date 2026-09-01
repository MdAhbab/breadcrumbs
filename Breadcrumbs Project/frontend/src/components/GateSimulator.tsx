import { useEffect, useRef, useState } from 'react';

import { GATE_PROMOTE, GATE_REJECT, GATE_STEPS, type GateDecision } from '../lib/data';
import { bp, bpDelta } from '../lib/format';
import { useReducedMotion } from '../lib/useMotionPref';
import { Seal } from './ui';
import './gate.css';

type Phase = 'idle' | 'running' | 'promote' | 'reject';

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

  const shown = result ?? GATE_PROMOTE;
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
              Submit a candidate model and watch the contract decide. One of these has
              quietly forgotten something the network already knew.
            </p>
            <div className="gate__actions">
              <button type="button" className="btn btn--primary btn--md" onClick={() => run(GATE_PROMOTE)}>
                Submit a good candidate
              </button>
              <button type="button" className="btn btn--onDark btn--md" onClick={() => run(GATE_REJECT)}>
                Submit a forgetful candidate
              </button>
            </div>
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

        {settled && (
          <div className={`outcome outcome--${phase}`} aria-live="polite">
            <Seal tone={phase === 'promote' ? 'sealed' : 'broken'} dark>
              {phase === 'promote' ? 'Promoted' : 'Rejected'}
            </Seal>
            <h3 className="outcome__head">
              {phase === 'promote'
                ? 'Nothing was forgotten.'
                : 'It forgot an earlier task.'}
            </h3>
            <p className="outcome__reason mono">{shown.reason}</p>

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
                {shown.perTask.map((t) => (
                  <tr key={t.taskId} className={t.pass ? '' : 'is-fail'}>
                    <th scope="row">
                      {t.label}
                      {t.isNewTask && <span className="gate__new stamp-type">new</span>}
                    </th>
                    <td className="mono">{bp(t.previousBp)}%</td>
                    <td className="mono">{bp(t.candidateBp)}%</td>
                    <td className={`mono ${t.pass ? 'ok' : 'bad'}`}>{bpDelta(t.changeBp)}</td>
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
                Try the other candidate
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
