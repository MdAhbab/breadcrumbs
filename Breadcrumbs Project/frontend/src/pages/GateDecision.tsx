import { ShieldCheck } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { GateSimulator } from '../components/GateSimulator';
import { Result } from '../components/states';
import { Tech } from '../components/Tech';
import { useDetail } from '../lib/detail';
import { plainReason, updateName, updateNumbers } from '../lib/plainReason';
import { HashChip, LedgerRow, Seal } from '../components/ui';
import { api, shortMsp, taskLabel, type GateDecision, type ModelVersion } from '../lib/api';
import { bp, bpDelta, dateTime, longDate } from '../lib/format';
import { useApi } from '../lib/useApi';
import './gatepage.css';

/**
 * AI model approvals.
 *
 * The verdict first in plain words, then the per-task table where a failing
 * row is unmissable, then the agreed rule, then who tested it. Stored ids,
 * hashes and the contract's exact wording sit behind "Technical detail".
 *
 * Every number is the contract's record of an evaluation that actually ran.
 */
export default function GateDecisionPage() {
  const { id } = useParams();
  return id ? <OneDecision id={id} /> : <DecisionIndex />;
}

/** Without an update named, the list of every decision. */
function DecisionIndex() {
  const registry = useApi(() => api.registry(), []);

  return (
    <div className="gatepage grain warp">
      <div className="gatepage__inner">
        <header className="gatepage__head">
          <div className="gv">
            <h1 className="gv__head">AI model approvals</h1>
            <p className="lead gv__body">
              Each update to the shared AI model is tested on everything it already
              knew. If it got worse at any of it, it is refused.
            </p>
          </div>
        </header>

        <section className="gpsec">
          <Result
            query={registry}
            pendingLabel="Reading the AI model updates"
            isEmpty={(rows) => rows.length === 0}
            empty={{
              title: 'No decisions yet',
              detail: 'The tests are ready, but no update has been put to them.',
            }}
          >
            {(rows: ModelVersion[]) => {
              const numbers = updateNumbers(rows);
              return (
                <table className="gptable gptable--index">
                  <thead>
                    <tr>
                      <th scope="col">Update</th>
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
                            <Link to={`/model/gate/${encodeURIComponent(m.model_id)}`}>
                              {updateName(m.model_id, numbers)}
                            </Link>
                            <Tech>
                              <span className="mono gptable__id">
                                {m.model_id} · {m.round_id} · built on {m.parent_id}
                              </span>
                            </Tech>
                          </th>
                          <td className="gptable__date">{longDate(m.decided_at)}</td>
                          <td>
                            <span className={`gpverdict stamp-type ${m.status === 'rejected' ? 'bad' : 'ok'}`}>
                              {m.status === 'rejected' ? 'Refused' : 'Approved'}
                            </span>
                          </td>
                          <td className="gptable__reason">
                            <Reason text={m.outcome_reason} />
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              );
            }}
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
  // The list is read too, only to name the update the same way as everywhere else.
  const query = useApi(
    () => Promise.all([api.decision(id), api.registry().catch(() => [] as ModelVersion[])]),
    [id],
  );

  return (
    <div className="gatepage grain warp">
      <div className="gatepage__inner">
        <Result query={query} pendingLabel="Reading the decision">
          {([d, rows]: [GateDecision, ModelVersion[]]) => {
            const rejected = d.outcome === 'reject';
            const cumulative = d.reason_code === 'CUMULATIVE_REGRESSION';
            const sigma = d.parameters.sigma_bp ?? 0;
            const name = updateName(d.candidate_id, updateNumbers(rows));

            return (
              <>
                <header className="gatepage__head">
                  <p className="stamp-type gatepage__eyebrow">
                    <Link to="/model/gate">AI model approvals</Link>
                    <Tech> · {d.round_id}</Tech>
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
                      {name}, {longDate(d.decided_at)}. <Reason text={d.reason} />
                    </p>
                  </div>
                </header>

                <section className="gpsec">
                  <h2 className="gpsec__title">Tested on every task</h2>
                  <div className="gptable-wrap scroll-x--dark">
                    <table className="gptable">
                      <thead>
                        <tr>
                          <th scope="col">Task</th>
                          <Tech><th scope="col">Test set</th></Tech>
                          <th scope="col">Before</th>
                          <th scope="col">After</th>
                          <th scope="col">Change</th>
                          <Tech>
                            <th scope="col">Best ever</th>
                            <th scope="col">Below best</th>
                            <th scope="col">Limit</th>
                          </Tech>
                          <th scope="col">Result</th>
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
                            <Tech>
                              <td className="mono dim">
                                {t.best_bp === null ? (
                                  <span className="gptable__none">none yet</span>
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
                            </Tech>
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
                    The tests were fixed before the update was made, so nobody could pick
                    them after seeing the result.
                  </p>
                </section>

                <section className="gpsec">
                  <h2 className="gpsec__title">The rule the members agreed</h2>
                  <div className="rules">
                    <Rule
                      label="Must get better at the new task by at least"
                      value={`${bp(d.parameters.gamma_bp)}%`}
                      sym="γ"
                    />
                    <Rule
                      label="May get worse at an old task by at most"
                      value={`${bp(d.parameters.tau_bp)}%`}
                      sym="τ"
                    />
                    <Rule
                      label="May fall below its best ever by at most"
                      value={d.parameters.sigma_bp ? `${bp(d.parameters.sigma_bp)}%` : 'not set'}
                      sym="σ"
                    />
                    <Rule
                      label="Members who must test it"
                      value={`${d.parameters.k}`}
                      sym="k"
                    />
                    <Rule
                      label="Their results may differ by at most"
                      value={`${bp(d.parameters.delta_bp)}%`}
                      sym="δ"
                    />
                  </div>
                </section>

                <section className="gpsec">
                  <h2 className="gpsec__title">Who tested it</h2>
                  <p className="small gpsec__lede">
                    Each member tested the update on its own machines and signed its
                    results.
                  </p>
                  <div className="endorsers">
                    {d.endorsers.map((msp) => (
                      <div key={msp} className="endorser">
                        <div className="endorser__top">
                          <span className="endorser__org">{shortMsp(msp)}</span>
                          <span className="endorser__agree stamp-type ok">accepted</span>
                        </div>
                        <Tech><p className="mono endorser__msp">{msp}</p></Tech>
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
                    <span className="stamp-type">Trained by</span>
                    <span className="mono median__v">
                      {d.contributors.map(shortMsp).join(' · ')}
                    </span>
                  </div>
                </section>

                <section className="gpsec">
                  <Tech>
                    <h2 className="gpsec__title">What was written to the ledger</h2>
                    <div className="gprecord">
                      <LedgerRow label="Outcome" dark>
                        {rejected ? 'Refused' : 'Approved'} ·{' '}
                        <span className="mono">{d.reason_code}</span>
                      </LedgerRow>
                      <LedgerRow label="Decided" dark>{dateTime(d.decided_at)}</LedgerRow>
                      <LedgerRow label="Update" dark>
                        <span className="mono">{d.candidate_id}</span>
                      </LedgerRow>
                      <LedgerRow label="Update fingerprint" dark>
                        <HashChip value={d.candidate_hash} dark />
                      </LedgerRow>
                      <LedgerRow label="Built on" dark>
                        <span className="mono">{d.parent_id}</span>
                      </LedgerRow>
                      <LedgerRow label="Round" dark>
                        <span className="mono">{d.round_id}</span>
                      </LedgerRow>
                      <LedgerRow label="Shared memory" dark>
                        <HashChip value={d.memory_bank_hash} dark />
                      </LedgerRow>
                      <LedgerRow label="Tested by" dark>{d.endorsers.join(', ')}</LedgerRow>
                    </div>
                  </Tech>

                  <div className="recompute">
                    <ShieldCheck size={17} />
                    <div>
                      <p className="recompute__head">Anyone can check this again</p>
                      <p className="small recompute__body">
                        Every input is on the ledger. Any member can work out this result
                        again and get the same answer.
                      </p>
                    </div>
                    <Link to="/model/registry" className="btn btn--onDark btn--sm">
                      AI model history
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
      <Tech><span className="rule__sym">{sym}</span></Tech>
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
