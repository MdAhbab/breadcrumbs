import { Link } from 'react-router-dom';

import { Result } from '../components/states';
import { Tech } from '../components/Tech';
import { Disclosure, HashChip, Seal } from '../components/ui';
import {
  api, taskLabel,
  type Benchmark, type DetectorStatus, type HighWater, type MemoryBank,
  type ModelVersion, type TrainingRound,
} from '../lib/api';
import { bp, bpDelta, commas, longDate } from '../lib/format';
import { useApi } from '../lib/useApi';
import './registry.css';

const TASK_LABEL: Record<string, string> = {
  wage_register_inconsistency: 'Wage register',
  forged_certificate: 'Certificates',
  chemical_misreporting: 'Chemical',
};

/**
 * Model lineage.
 *
 * Rejected versions stay in the list, with the reason they were refused. A
 * registry that shows only what shipped cannot answer the question an auditor
 * actually asks — what did you try, and why was it turned down?
 *
 * Every number here is the contract's record of an evaluation that ran: the
 * detector was trained, three organisations signed what they measured, and the
 * gate applied the rule. Nothing on this page was chosen to make a point.
 */
export default function ModelRegistry() {
  const world = useApi(
    () => Promise.all([
      api.registry(), api.currentModel(), api.rounds(), api.benchmarks(),
      api.memoryBank(), api.highWater(), api.detector(),
    ]) as Promise<[
      ModelVersion[], ModelVersion | null, TrainingRound[], Benchmark[], MemoryBank,
      HighWater, DetectorStatus,
    ]>,
    [],
  );

  return (
    <div className="reg">
      <header className="reg__head">
        <p className="stamp-type reg__eyebrow">Model history</p>
        <h1>Every version, approved and refused.</h1>
        <p className="lead reg__lede">
          Each update was tested against a set of problems fixed and published before
          that round opened, so nobody could pick the tests after seeing the result.
          The refusals are the interesting half of this list.
        </p>
      </header>

      <Result
        query={world}
        pendingLabel="Reading the model channel"
        isEmpty={([registry]) => registry.length === 0}
        empty={{
          title: 'No update has been tested yet',
          detail: 'The tests are published, but nothing has been put to them.',
        }}
      >
        {([registry, current, rounds, benchmarks, bank, highWater, deployed]) => (
          <>
          <ol className="lineage">
            {[...registry]
              .sort((a, b) => b.decided_at.localeCompare(a.decided_at))
              .map((m) => {
                const inForce = current?.model_id === m.model_id;
                return (
                  <li key={m.model_id} className={`ver is-${inForce ? 'in_force' : m.status}`}>
                    <div className="ver__spine" aria-hidden="true">
                      <span className="ver__node" />
                    </div>

                    <div className="ver__body">
                      <div className="ver__top">
                        <span className="mono ver__id">{m.model_id}</span>
                        <Seal
                          tone={
                            m.status === 'rejected' ? 'broken'
                              : m.status === 'superseded' ? 'inert' : 'sealed'
                          }
                        >
                          {inForce ? 'in force' : m.status}
                        </Seal>
                        <span className="small ver__date">{longDate(m.decided_at)}</span>
                      </div>

                      <p className="ver__reason">{m.outcome_reason}</p>

                      <div className="ver__acc">
                        {m.per_task.map((t) => (
                          <span key={t.task_id} className={`acc ${t.pass ? '' : 'is-fail'}`}>
                            <span className="stamp-type acc__t">
                              {TASK_LABEL[t.task_id] ?? t.task_id.replace(/_/g, ' ')}
                            </span>
                            <span className="mono acc__v">
                              {bp(t.candidate_bp)}%
                              <span className={`acc__d ${t.change_bp < 0 ? 'is-down' : 'is-up'}`}>
                                {' '}{bpDelta(t.change_bp)}
                              </span>
                            </span>
                            <span className="acc__bar" aria-hidden="true">
                              <span style={{ width: `${t.candidate_bp / 100}%` }} />
                            </span>
                          </span>
                        ))}
                      </div>

                      <div className="ver__foot">
                        <span className="small ver__meta">
                          parent <span className="mono">{m.parent_id}</span> ·{' '}
                          round <span className="mono">{m.round_id}</span> ·{' '}
                          {m.endorsers.length} organisations signed off
                        </span>
                        <Tech><HashChip value={m.memory_bank_hash} /></Tech>
                        <Link to={`/model/gate/${m.model_id}`} className="ver__link">
                          the decision →
                        </Link>
                      </div>
                    </div>
                  </li>
                );
              })}
          </ol>

          <Deployed status={deployed} inForce={current?.model_id ?? null} />
          <LearningPlane
            rounds={rounds}
            benchmarks={benchmarks}
            bank={bank}
            highWater={highWater}
          />
          </>
        )}
      </Result>
    </div>
  );
}

/**
 * What is actually running, as against what the gate promoted.
 *
 * These are two different facts and a page that showed only the first would be
 * reporting an intention. The registry is the ledger's record of which candidate
 * was approved; this is the file on disk the API will really load and score with.
 * They can disagree — a promotion nobody exported, or an artefact trained after
 * the last decision — and the reader should be able to see that.
 */
function Deployed({
  status, inForce,
}: {
  status: DetectorStatus;
  inForce: string | null;
}) {
  if (!status.trained) {
    return (
      <section className="deployed deployed--none">
        <p className="stamp-type plane__head">The deployed detector</p>
        <p className="plane__note">
          Nothing is deployed. The gate has promoted {inForce ?? 'no model'}, but no
          trained artefact is on disk, so the product cannot score a document.
        </p>
        <p className="small plane__note mono">{status.reason}</p>
      </section>
    );
  }

  const m = status.measured;
  const pc = (v: number | null | undefined) =>
    v === null || v === undefined ? 'n/a' : `${(v * 100).toFixed(1)}%`;

  return (
    <section className="deployed">
      <p className="stamp-type plane__head">The deployed detector</p>
      <div className="deployed__figures">
        <Figure n={String(status.parameters?.toLocaleString('en-GB'))} l="parameters" />
        <Figure n={`${Math.round((status.weights_bytes ?? 0) / 1024)} KB`} l="on disk" />
        <Figure n={String(status.features)} l="features per document" />
        <Figure n={pc(m?.detection)} l="of anomalies caught" />
        <Figure n={pc(m?.false_positive)} l="of clean documents flagged" />
        <Figure n={pc(m?.roc_auc)} l="ROC-AUC" />
      </div>

      <p className="plane__note">
        This is the whole of it: {status.parameters?.toLocaleString('en-GB')} parameters,
        about {Math.round((status.weights_bytes ?? 0) / 1024)} KB, running on the CPU inside
        the API process. There is no model server and no GPU. The threshold is{' '}
        {status.threshold?.toFixed(3)}, chosen for a {pc(status.false_positive_budget)}{' '}
        false-positive budget on a {status.chosen_on}.
      </p>

      {status.detection_by_kind && (
        <div className="deployed__kinds">
          <p className="stamp-type">Detection by anomaly kind</p>
          <ul className="plane__list">
            {Object.entries(status.detection_by_kind)
              .filter(([kind]) => kind !== 'clean')
              .sort((a, b) => (b[1] ?? 0) - (a[1] ?? 0))
              .map(([kind, rate]) => (
                <li key={kind} className="deployed__kind">
                  <span className="deployed__kindname">{kind.replace(/_/g, ' ')}</span>
                  <span className="deployed__kindbar" aria-hidden="true">
                    <span style={{ width: `${(rate ?? 0) * 100}%` }} />
                  </span>
                  <span className="mono">{pc(rate)}</span>
                </li>
              ))}
          </ul>
        </div>
      )}

      {status.blind_to && (
        <p className="plane__note plane__note--warn">
          <strong>It cannot see {status.blind_to.kind.replace(/_/g, ' ')}.</strong>{' '}
          {status.blind_to.why} At {pc(status.blind_to.detection)} it is indistinguishable
          from guessing, and that is the honest number rather than a failure to be fixed by
          more training.
        </p>
      )}

      <p className="plane__note">{status.note}</p>
    </section>
  );
}

function Figure({ n, l }: { n: string; l: string }) {
  return (
    <div className="deployed__fig">
      <span className="deployed__n">{n}</span>
      <span className="small">{l}</span>
    </div>
  );
}

/**
 * The rest of the learning plane: what was sealed, what was run, what is shared.
 *
 * These three are usually left off a model page, and leaving them off is what
 * lets a federated-learning claim go unchecked. The benchmarks matter because
 * they were committed by hash *before* the round opened, so the organisations
 * training could not hold the set they would be judged against. The memory bank
 * matters because it is the only thing that crosses between members, and its
 * privacy note is served from the model package so no screen can soften it.
 */
function LearningPlane({
  rounds, benchmarks, bank, highWater,
}: {
  rounds: TrainingRound[];
  benchmarks: Benchmark[];
  bank: MemoryBank;
  highWater: HighWater;
}) {
  return (
    <section className="plane">
      <h2 className="reg__h2">The rest of the learning plane</h2>

      <div className="plane__grid">
        <div className="plane__col">
          <p className="stamp-type plane__head">The tests, fixed before any training began</p>
          <ul className="plane__list">
            {benchmarks.map((b) => (
              <li key={b.task_id} className="plane__row">
                <span className="plane__what">{taskLabel(b.task_id)}</span>
                <span className="small dim">
                  {commas(b.size)} rows held back · fixed on {longDate(b.committed_at)}
                </span>
                <Tech><HashChip value={b.benchmark_hash} /></Tech>
                <Seal tone={b.revealed ? 'inert' : 'sealed'}>
                  {b.revealed ? 'revealed' : 'still sealed'}
                </Seal>
              </li>
            ))}
          </ul>
          <p className="small plane__note">
            A sealed row shows only its hash. That is the anti-gaming design: training on
            the benchmark would take collusion rather than being something any member
            could do quietly.
          </p>
        </div>

        <div className="plane__col">
          <p className="stamp-type plane__head">Rounds</p>
          <ul className="plane__list">
            {rounds.map((r) => (
              <li key={r.round_id} className="plane__row">
                <span className="plane__what mono">{r.round_id}</span>
                <span className="small dim">
                  {r.contributors.length} contributors · opened {longDate(r.opened_at)}
                </span>
                <span className="small dim">{r.tasks.map(taskLabel).join(' · ')}</span>
                <Seal tone={r.decision === 'promote' ? 'sealed' : r.decision ? 'broken' : 'pending'}>
                  {r.decision ?? r.status}
                </Seal>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="plane__col plane__col--wide">
        <p className="stamp-type plane__head">
          Best score ever reached, which is what the slow-erosion limit is measured against
        </p>
        <ul className="plane__list">
          {Object.entries(highWater.marks).map(([task, mark]) => (
            <li key={task} className="plane__row plane__row--tight">
              <span className="plane__what">{taskLabel(task)}</span>
              {mark === null ? (
                <span className="small dim plane__nobase">
                  no baseline yet, nothing approved on this task
                </span>
              ) : (
                <span className="mono">{bp(mark)}%</span>
              )}
            </li>
          ))}
        </ul>
        <p className="small plane__note">{highWater.note}</p>
        <p className="small plane__note">
          The gate bounds loss twice: against the model in force this round, and against
          the best a task has ever reached. The second exists because the first is not a
          limit at all across many rounds. An update giving up slightly less than the
          per-round limit every time would be promoted every time, and the model would
          erode with no single decision ever being wrong.
        </p>
      </div>

      <Disclosure summary="What the shared memory actually holds">
        <p className="plane__note">{bank.contains}</p>
        <p className="plane__note plane__note--warn">{bank.privacy_note}</p>
        <ul className="plane__list">
          {bank.anchored_hashes.map((h) => (
            <li key={h.round_id} className="plane__row plane__row--tight">
              <span className="mono">{h.round_id}</span>
              <Tech><HashChip value={h.memory_bank_hash} /></Tech>
            </li>
          ))}
        </ul>
        <p className="small plane__note">
          A fingerprint of what was shared in each round is on the ledger, so what
          actually changed hands can be checked afterwards rather than taken on trust.
        </p>
      </Disclosure>
    </section>
  );
}
