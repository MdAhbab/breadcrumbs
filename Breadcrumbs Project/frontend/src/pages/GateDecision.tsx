import { ShieldCheck } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { GateSimulator } from '../components/GateSimulator';
import { Result } from '../components/states';
import { Tech } from '../components/Tech';
import { useDetail } from '../lib/detail';
import { plainReason } from '../lib/plainReason';
import { HashChip, LedgerRow, Seal } from '../components/ui';
import { api, shortMsp, taskLabel, type GateDecision, type ModelVersion } from '../lib/api';
import { bp, bpDelta, dateTime, longDate } from '../lib/format';
import { useApi } from '../lib/useApi';
import './gatepage.css';

/**
 * The Continuity Gate decision.
 *
 * The most important screen in the product, and the one a judge will be shown.
 * It has fifteen seconds to make a smart-contract decision legible to someone
 * who has never heard of continual learning.
 *
 * So: the verdict first in plain English, then the per-task table where a
 * failing row is unmissable among passing ones, then the rule it was judged
 * against, then who signed what. The lock mechanism from the landing page
 * reappears, so the marketing surface and the product share a physical
 * vocabulary rather than merely a palette.
 *
 * Every number is the contract's record of an evaluation that actually ran. The
 * page used to pick between two hand-written decisions on `id === 'm-v8-rc1'`,
 * which meant the screen making the product's strongest claim was the one
 * screen guaranteed to agree with itself.
 */
export default function GateDecisionPage() {
  const { id } = useParams();
  return id ? <OneDecision id={id} /> : <DecisionIndex />;
}

/** Without a candidate named, the docket of every decision on the channel. */
function DecisionIndex() {
  const registry = useApi(() => api.registry(), []);

  return (
    <div className="gatepage grain warp">
      <div className="gatepage__inner">
        <header className="gatepage__head">
          <p className="stamp-type gatepage__eyebrow">Model approvals</p>
          <div className="gv">
            <h1 className="gv__head">Every update, approved and refused.</h1>
            <p className="lead gv__body">
              The members share one detector, and it is updated in rounds. Before an
              update is allowed to replace the one in use, a contract re-tests it on
              every problem the model had already solved. If the update is worse at any
              of them it is refused, and that refusal is written down just as permanently
              as an approval. Open one to see what it was tested on and who signed it.
            </p>
          </div>
        </header>

        <section className="gpsec">
          <Result
            query={registry}
            pendingLabel="Reading the model channel"
            isEmpty={(rows) => rows.length === 0}
            empty={{
              title: 'No decisions yet',
              detail: 'The tests are fixed and published, but no update has been put to them.',
            }}
          >
            {(rows: ModelVersion[]) => (
              <div className="gptable-wrap scroll-x--dark">
                <table className="gptable">
                  <thead>
                    <tr>
                      <th scope="col">Update</th>
                      <th scope="col">Round</th>
                      <Tech><th scope="col">Built on</th></Tech>
                      <th scope="col">Decided</th>
                      <th scope="col">Outcome</th>
                      <th scope="col">Why</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...rows]
                      .sort((a, b) => b.decided_at.localeCompare(a.decided_at))
                      .map((m) => (
                        <tr key={m.model_id} className={m.status === 'rejected' ? 'is-fail' : ''}>
                          <th scope="row">
                            <Link to={`/model/gate/${encodeURIComponent(m.model_id)}`} className="mono">
                              {m.model_id}
                            </Link>
                          </th>
                          <td className="mono">{m.round_id}</td>
                          <Tech><td className="mono dim">{m.parent_id}</td></Tech>
                          <td className="mono dim">{longDate(m.decided_at)}</td>
                          <td>
                            <span className={`gpverdict stamp-type ${m.status === 'rejected' ? 'bad' : 'ok'}`}>
                              {m.status === 'rejected' ? 'refused' : 'approved'}
                            </span>
                          </td>
                          <td className="gptable__reason">
                            <span><Reason text={m.outcome_reason} /></span>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </Result>
        </section>

        <section className="gpsec">
          <h2 className="gpsec__title">Replay a decision</h2>
          <GateSimulator />
        </section>
      </div>
    </div>
  );
}

function OneDecision({ id }: { id: string }) {
  const query = useApi(() => api.decision(id), [id]);

  return (
    <div className="gatepage grain warp">
      <div className="gatepage__inner">
        <Result query={query} pendingLabel="Reading the decision off the chain">
          {(d: GateDecision) => {
            const rejected = d.outcome === 'reject';
            const cumulative = d.reason_code === 'CUMULATIVE_REGRESSION';
            const failing = d.per_task.find((t) => !t.pass);
            const newTask = d.per_task.find((t) => t.is_new_task);
            // The task that broke the cumulative bound, which is not necessarily
            // the same row as the one that failed the per-round check.
            const sigma = d.parameters.sigma_bp ?? 0;
            const drifting = d.per_task.find(
              (t) => !t.is_new_task
                && t.drift_from_best_bp !== null
                && t.drift_from_best_bp > sigma,
            );

            return (
              <>
                <header className="gatepage__head">
                  <p className="stamp-type gatepage__eyebrow">
                    Model approvals · round {d.round_id}
                  </p>

                  <div className={`gv gv--${d.outcome}`}>
                    <Seal tone={rejected ? 'broken' : 'sealed'} dark>
                      {rejected ? 'Refused' : 'Approved'}
                    </Seal>
                    <h1 className="gv__head">
                      {!rejected
                        ? 'Approved. It improved without forgetting anything.'
                        : cumulative
                          ? 'Refused. It has slipped too far from its own best.'
                          : 'Refused. It forgot something it had already learned.'}
                    </h1>
                    <p className="lead gv__body">
                      {!rejected ? (
                        <>
                          Model <span className="mono">{d.candidate_id}</span> improved on
                          the new problem, and lost no more than the agreed margin on any
                          earlier one. That holds both for this round and against its own
                          best score. It is now the model everyone uses.
                        </>
                      ) : cumulative && drifting ? (
                        <>
                          Model <span className="mono">{d.candidate_id}</span> passed every
                          per-round check. But{' '}
                          {taskLabel(drifting.task_id).toLowerCase()} has now fallen{' '}
                          {Math.abs((drifting.drift_from_best_bp ?? 0) / 100).toFixed(1)}{' '}
                          points below the best it ever reached. The agreed limit is{' '}
                          {bp(d.parameters.sigma_bp ?? 0)}.
                          <br />
                          This is the limit that catches slow erosion: an update can give
                          up a little every round, each one defensible on its own, until
                          the model is ruined and no single refusal was ever warranted.
                        </>
                      ) : failing ? (
                        <>
                          Model <span className="mono">{d.candidate_id}</span>
                          {newTask && (
                            <>
                              {' '}improved on {taskLabel(newTask.task_id).toLowerCase()} by{' '}
                              {bpDelta(newTask.change_bp)} points,
                            </>
                          )}{' '}
                          but lost {Math.abs(failing.change_bp / 100).toFixed(1)} points on{' '}
                          {taskLabel(failing.task_id).toLowerCase()}, which the network
                          already knew. <span className="mono">{d.parent_id}</span> was not
                          replaced by it.
                        </>
                      ) : (
                        <>
                          Model <span className="mono">{d.candidate_id}</span> was refused.
                        </>
                      )}
                    </p>
                    <p className="small gv__body">{d.reason}</p>
                  </div>
                </header>

                <section className="gpsec">
                  <h2 className="gpsec__title">Measured against every task the network knows</h2>
                  <div className="gptable-wrap scroll-x--dark">
                    <table className="gptable">
                      <thead>
                        <tr>
                          <th scope="col">Task</th>
                          <th scope="col">Benchmark</th>
                          <th scope="col">{d.parent_id}</th>
                          <th scope="col">{d.candidate_id}</th>
                          <th scope="col">Change</th>
                          <th scope="col">Best ever</th>
                          <th scope="col">Below best</th>
                          <th scope="col">Tolerance</th>
                          <th scope="col">Verdict</th>
                        </tr>
                      </thead>
                      <tbody>
                        {d.per_task.map((t) => (
                          <tr key={t.task_id} className={t.pass ? '' : 'is-fail'}>
                            <th scope="row">
                              {taskLabel(t.task_id)}
                              {t.is_new_task && (
                                <span className="gptable__new stamp-type">new task</span>
                              )}
                            </th>
                            <Tech><td><HashChip value={t.benchmark_hash} dark /></td></Tech>
                            <td className="mono">{bp(t.previous_bp)}%</td>
                            <td className="mono">{bp(t.candidate_bp)}%</td>
                            <td className={`mono ${t.pass ? 'ok' : 'bad'}`}>
                              {bpDelta(t.change_bp)}
                            </td>
                            <td className="mono dim">
                              {t.best_bp === null ? (
                                <span className="gptable__none">no baseline yet</span>
                              ) : (
                                `${bp(t.best_bp)}%`
                              )}
                            </td>
                            <td className="mono">
                              {t.drift_from_best_bp === null ? (
                                <span className="gptable__none">n/a</span>
                              ) : t.drift_from_best_bp <= 0 ? (
                                <span className="ok">at or above it</span>
                              ) : (
                                <span className={t.drift_from_best_bp > sigma ? 'bad' : ''}>
                                  {bp(t.drift_from_best_bp)}
                                </span>
                              )}
                            </td>
                            <td className="mono dim">
                              {t.is_new_task
                                ? `≥ +${bp(t.threshold_bp)}`
                                : `≥ ${bp(t.threshold_bp)}, and ≤ ${bp(sigma)} below best`}
                            </td>
                            <td>
                              <span className={`gpverdict stamp-type ${t.pass ? 'ok' : 'bad'}`}>
                                {t.pass ? 'pass' : 'fail'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="small gpsec__note">
                    Every benchmark hash above was committed to the ledger <em>before</em>{' '}
                    this round opened, and revealed only after the decision. The
                    organisations training in a round do not hold the set they will be
                    judged against.
                  </p>
                  <p className="small gpsec__note">
                    <strong>Best ever</strong> is the highest score a task has reached under
                    an <em>approved</em> model, so a refused update cannot raise the bar it
                    will be measured against next time. &ldquo;No baseline yet&rdquo; means
                    nothing has been approved on that task, so there is no history to have
                    drifted from, which is not the same as having drifted by zero.
                  </p>
                </section>

                <section className="gpsec">
                  <h2 className="gpsec__title">The rule the consortium agreed</h2>
                  <div className="rules">
                    <Rule
                      label="Minimum gain on the new task"
                      value={`+${bp(d.parameters.gamma_bp)} points`}
                      sym="γ"
                    />
                    <Rule
                      label="Maximum loss on any earlier task, this round"
                      value={`${bp(d.parameters.tau_bp)} points`}
                      sym="τ"
                    />
                    <Rule
                      label="Maximum fall below a task's best ever"
                      value={
                        d.parameters.sigma_bp
                          ? `${bp(d.parameters.sigma_bp)} points`
                          : 'not recorded'
                      }
                      sym="σ"
                    />
                    <Rule
                      label="Independent organisations required"
                      value={`${d.parameters.k}`}
                      sym="k"
                    />
                    <Rule
                      label="Tolerated disagreement between them"
                      value={`${bp(d.parameters.delta_bp)} points`}
                      sym="δ"
                    />
                  </div>
                </section>

                <section className="gpsec">
                  <h2 className="gpsec__title">Who evaluated it, and what they signed</h2>
                  <p className="small gpsec__lede">
                    The contract does not run the model. It cannot: the weights are
                    off-chain, and a floating-point forward pass is not identical across
                    hardware. Each organisation evaluated the candidate itself and signed
                    the accuracies it measured. The contract resolved each certificate
                    through the MSP, verified the signature against the key inside it,
                    checked the organisations agreed within δ, and took the median.
                  </p>
                  <div className="endorsers">
                    {d.endorsers.map((msp) => (
                      <div key={msp} className="endorser">
                        <div className="endorser__top">
                          <span className="endorser__org">{shortMsp(msp)}</span>
                          <span className="endorser__agree stamp-type ok">accepted</span>
                        </div>
                        <p className="mono endorser__msp">{msp}</p>
                        <p className="small endorser__foot">
                          Signature verified against the certificate the MSP holds for this
                          organisation, and its figures agreed with the others within δ.
                        </p>
                      </div>
                    ))}
                  </div>

                  {d.rejected_submissions.length > 0 && (
                    <div className="endorsers">
                      {d.rejected_submissions.map((r, i) => (
                        <div key={`${r.endorser_msp}-${i}`} className="endorser endorser--out">
                          <div className="endorser__top">
                            <span className="endorser__org">{shortMsp(r.endorser_msp)}</span>
                            <span className="endorser__agree stamp-type bad">refused</span>
                          </div>
                          <p className="small endorser__foot">{r.reason}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="median">
                    <span className="stamp-type">Contributing organisations</span>
                    <span className="mono median__v">
                      {d.contributors.map(shortMsp).join(' · ')}
                    </span>
                  </div>
                </section>

                <section className="gpsec">
                  <h2 className="gpsec__title">Replay the decision</h2>
                  <GateSimulator decision={d} compact />
                </section>

                <section className="gpsec">
                  <h2 className="gpsec__title">What was written to the ledger</h2>
                  <div className="gprecord">
                    <LedgerRow label="Outcome" dark>
                      {rejected ? 'Refused' : 'Approved'} ·{' '}
                      <span className="mono">{d.reason_code}</span>
                    </LedgerRow>
                    <LedgerRow label="Decided" dark>{dateTime(d.decided_at)}</LedgerRow>
                    <LedgerRow label="Candidate hash" dark>
                      <HashChip value={d.candidate_hash} dark />
                    </LedgerRow>
                    <LedgerRow label="Parent model" dark>
                      <span className="mono">{d.parent_id}</span>
                    </LedgerRow>
                    <LedgerRow label="Round" dark>
                      <span className="mono">{d.round_id}</span>
                    </LedgerRow>
                    <LedgerRow label="Memory bank" dark>
                      <HashChip value={d.memory_bank_hash} dark />
                    </LedgerRow>
                    <LedgerRow label="Endorser set" dark>{d.endorsers.join(', ')}</LedgerRow>
                  </div>

                  <div className="recompute">
                    <ShieldCheck size={17} />
                    <div>
                      <p className="recompute__head">Verify this decision yourself</p>
                      <p className="small recompute__body">
                        Every input is on the ledger: the benchmark hashes, the signed
                        metrics, the endorser set and the parameters. Any member can
                        work this outcome out again and get the same answer. The table above
                        is what the contract recorded, not a summary of it.
                      </p>
                    </div>
                    <Link to="/model/registry" className="btn btn--onDark btn--sm">
                      See the lineage
                    </Link>
                  </div>
                </section>
              </>
            );
          }}
        </Result>
      </div>
    </div>
  );
}

function Rule({ label, value, sym }: { label: string; value: string; sym: string }) {
  return (
    <div className="rule">
      <span className="rule__sym">{sym}</span>
      <div>
        <p className="rule__label small">{label}</p>
        <p className="rule__value mono">{value}</p>
      </div>
    </div>
  );
}

/**
 * The contract's reason, in whichever register the reader asked for.
 *
 * The stored string is a ledger record and never changes; this only decides
 * which of the two wordings is on screen.
 */
function Reason({ text }: { text: string }) {
  const { technical } = useDetail();
  return <>{technical ? text : plainReason(text)}</>;
}
