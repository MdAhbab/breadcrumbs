import { Link } from 'react-router-dom';

import { Result } from '../components/states';
import { Tech } from '../components/Tech';
import { HashChip, Seal } from '../components/ui';
import {
  api, taskLabel,
  type Benchmark, type DetectorStatus, type HighWater, type MemoryBank,
  type ModelVersion, type TrainingRound,
} from '../lib/api';
import { useDetail } from '../lib/detail';
import { bp, bpDelta, commas, longDate } from '../lib/format';
import { plainReason, updateName, updateNumbers } from '../lib/plainReason';
import { useApi } from '../lib/useApi';
import './registry.css';

const TASK_LABEL: Record<string, string> = {
  wage_register_inconsistency: 'Wage register',
  forged_certificate: 'Certificates',
  chemical_misreporting: 'Chemical',
};

/** What the AI model misses, in words. Anything not listed shows its own name. */
const BLIND_LABEL: Record<string, string> = {
  cross_inconsistency: 'two documents that each look fine but disagree with each other',
};

/**
 * AI model history.
 *
 * Refused updates stay in the list, with the reason they were refused. A list
 * that shows only what shipped cannot answer what was tried and turned down.
 * Status words and reasons match AI model approvals (lib/plainReason).
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

  const { technical } = useDetail();

  return (
    <div className="reg">
      <header className="reg__head">
        <h1>AI model history</h1>
        <p className="lead reg__lede">
          Every update to the shared AI model, newest first. Refused updates stay on
          the list with the reason.
        </p>
      </header>

      <Result
        query={world}
        pendingLabel="Reading the AI model history"
        isEmpty={([registry]) => registry.length === 0}
        empty={{
          title: 'No update has been tested yet',
          detail: 'The tests are ready, but no update has been put to them.',
        }}
      >
        {([registry, current, rounds, benchmarks, bank, highWater, deployed]) => {
          const numbers = updateNumbers(registry);
          return (
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
                        <span className="ver__id">{updateName(m.model_id, numbers)}</span>
                        <Tech><span className="mono small dim">{m.model_id}</span></Tech>
                        <Seal
                          tone={
                            m.status === 'rejected' ? 'broken'
                              : m.status === 'superseded' ? 'inert' : 'sealed'
                          }
                        >
                          {statusWord(m.status, inForce)}
                        </Seal>
                        <span className="small ver__date">{longDate(m.decided_at)}</span>
                      </div>

                      <p className="ver__reason">
                        {technical ? m.outcome_reason : plainReason(m.outcome_reason)}
                      </p>

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
                          Tested by {commas(m.endorsers.length)} members
                          <Tech>
                            {' '}· built on <span className="mono">{m.parent_id}</span> ·{' '}
                            <span className="mono">{m.round_id}</span>
                          </Tech>
                        </span>
                        <Tech><HashChip value={m.memory_bank_hash} /></Tech>
                        <Link to={`/model/gate/${m.model_id}`} className="ver__link">
                          See the decision →
                        </Link>
                      </div>
                    </div>
                  </li>
                );
              })}
          </ol>

          <Deployed status={deployed} />
          <Tech>
            <LearningPlane
              rounds={rounds}
              benchmarks={benchmarks}
              bank={bank}
              highWater={highWater}
            />
          </Tech>
          </>
          );
        }}
      </Result>
    </div>
  );
}

/** Refused, Approved or In use: the same three words as AI model approvals. */
function statusWord(status: ModelVersion['status'], inForce: boolean): string {
  if (inForce) return 'In use';
  return status === 'rejected' ? 'Refused' : 'Approved';
}

/**
 * The AI model actually running, as against what was approved.
 *
 * Two different facts: the list above is what the members approved, this is
 * the file the API really scores with. One plain line says what it catches and
 * what it misses; the measurements behind that line are technical detail.
 */
function Deployed({ status }: { status: DetectorStatus }) {
  if (!status.trained) {
    return (
      <section className="deployed deployed--none">
        <p className="stamp-type plane__head">The AI model in use</p>
        <p className="plane__note">No AI model is running yet, so documents cannot be scored.</p>
        <Tech><p className="small plane__note mono">{status.reason}</p></Tech>
      </section>
    );
  }

  const m = status.measured;
  const pc = (v: number | null | undefined) =>
    v === null || v === undefined ? 'n/a' : `${(v * 100).toFixed(1)}%`;
  const blind = status.blind_to
    ? BLIND_LABEL[status.blind_to.kind] ?? status.blind_to.kind.replace(/_/g, ' ')
    : null;

  return (
    <section className="deployed">
      <p className="stamp-type plane__head">The AI model in use</p>
      <p className="deployed__sum">
        It catches {pc(m?.detection)} of problems in a document. It wrongly flags{' '}
        {pc(m?.false_positive)} of clean documents.
        {blind && <> It cannot catch {blind}.</>}
      </p>

      <Tech>
        <div className="deployed__figures">
          <Figure n={String(status.parameters?.toLocaleString('en-GB'))} l="parameters" />
          <Figure n={`${Math.round((status.weights_bytes ?? 0) / 1024)} KB`} l="on disk" />
          <Figure n={String(status.features)} l="features per document" />
          <Figure n={pc(m?.roc_auc)} l="ROC-AUC" />
        </div>

        <p className="plane__note">
          Runs on the CPU inside the API process. Threshold{' '}
          {status.threshold?.toFixed(3)}, chosen for a {pc(status.false_positive_budget)}{' '}
          false-positive budget on a {status.chosen_on}.
        </p>

        {status.detection_by_kind && (
          <div className="deployed__kinds">
            <p className="stamp-type">Caught, by kind of problem</p>
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

        {status.blind_to && <p className="plane__note">{status.blind_to.why}</p>}
        <p className="plane__note">{status.note}</p>
      </Tech>
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
 * Tests, rounds, best scores and the shared memory: technical detail only.
 *
 * The tests were fixed by fingerprint before each round opened, so nobody
 * training could hold the set they would be judged against. The shared memory
 * is the only thing that crosses between members, and its privacy note is
 * served from the model package so no screen can soften it.
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
      <h2 className="reg__h2">Tests, rounds and shared memory</h2>

      <div className="plane__grid">
        <div className="plane__col">
          <p className="stamp-type plane__head">Tests, fixed before any training began</p>
          <ul className="plane__list">
            {benchmarks.map((b) => (
              <li key={b.task_id} className="plane__row">
                <span className="plane__what">{taskLabel(b.task_id)}</span>
                <span className="small dim">
                  {commas(b.size)} rows held back · fixed on {longDate(b.committed_at)}
                </span>
                <HashChip value={b.benchmark_hash} />
                <Seal tone={b.revealed ? 'inert' : 'sealed'}>
                  {b.revealed ? 'revealed' : 'still hidden'}
                </Seal>
              </li>
            ))}
          </ul>
        </div>

        <div className="plane__col">
          <p className="stamp-type plane__head">Rounds</p>
          <ul className="plane__list">
            {rounds.map((r) => (
              <li key={r.round_id} className="plane__row">
                <span className="plane__what mono">{r.round_id}</span>
                <span className="small dim">
                  {r.contributors.length} members trained it · opened {longDate(r.opened_at)}
                </span>
                <Seal tone={r.decision === 'promote' ? 'sealed' : r.decision ? 'broken' : 'pending'}>
                  {r.decision === 'promote' ? 'Approved'
                    : r.decision ? 'Refused' : 'Waiting'}
                </Seal>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="plane__col plane__col--wide">
        <p className="stamp-type plane__head">Best score ever reached</p>
        <ul className="plane__list">
          {Object.entries(highWater.marks).map(([task, mark]) => (
            <li key={task} className="plane__row plane__row--tight">
              <span className="plane__what">{taskLabel(task)}</span>
              {mark === null ? (
                <span className="small dim plane__nobase">none yet</span>
              ) : (
                <span className="mono">{bp(mark)}%</span>
              )}
            </li>
          ))}
        </ul>
        <p className="small plane__note">{highWater.note}</p>
      </div>

      <div className="plane__col plane__col--wide">
        <p className="stamp-type plane__head">What the shared memory holds</p>
        <p className="plane__note">{bank.contains}</p>
        <p className="plane__note plane__note--warn">{bank.privacy_note}</p>
        <ul className="plane__list">
          {bank.anchored_hashes.map((h) => (
            <li key={h.round_id} className="plane__row plane__row--tight">
              <span className="mono">{h.round_id}</span>
              <HashChip value={h.memory_bank_hash} />
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
