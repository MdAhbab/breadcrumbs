import { ShieldCheck } from 'lucide-react';
import { useParams } from 'react-router-dom';

import { GateSimulator } from '../components/GateSimulator';
import { HashChip, LedgerRow, Seal } from '../components/ui';
import { GATE_PROMOTE, GATE_REJECT, orgName } from '../lib/data';
import { bp, bpDelta, commas, dateTime } from '../lib/format';
import './gatepage.css';

/**
 * The Continuity Gate decision.
 *
 * The most important screen in the product, and the one a judge will be shown.
 * It has fifteen seconds to make a smart-contract decision legible to someone
 * who has never heard of continual learning.
 *
 * So: the verdict first in plain English, then the per-task table where the
 * single failing row is unmissable among passing ones, then the rule it was
 * judged against, then who signed what. The lock mechanism from the landing
 * page reappears, so the marketing surface and the product share a physical
 * vocabulary rather than merely a palette.
 */
export default function GateDecisionPage() {
  const { id } = useParams();
  const d = id === 'm-v8-rc1' ? GATE_PROMOTE : GATE_REJECT;
  const rejected = d.outcome === 'reject';
  const failing = d.perTask.find((t) => !t.pass);

  return (
    <div className="gatepage grain warp">
      <div className="gatepage__inner">
        <header className="gatepage__head">
          <p className="stamp-type gatepage__eyebrow">
            Continuity Gate · round {d.roundId} · candidate {d.candidateId}
          </p>

          <div className={`gv gv--${d.outcome}`}>
            <Seal tone={rejected ? 'broken' : 'sealed'} dark>
              {rejected ? 'Rejected' : 'Promoted'}
            </Seal>
            <h1 className="gv__head">
              {rejected
                ? 'Candidate rejected — it forgot an earlier task.'
                : 'Candidate promoted — nothing was forgotten.'}
            </h1>
            <p className="lead gv__body">
              {rejected && failing ? (
                <>
                  Model <span className="mono">{d.candidateId}</span> improved on
                  chemical-inventory misreporting by{' '}
                  {bpDelta(d.perTask.find((t) => t.isNewTask)!.changeBp)} points, but lost{' '}
                  {Math.abs(failing.changeBp / 100).toFixed(1)} points on{' '}
                  {failing.label.toLowerCase()} — which the network already knew.{' '}
                  <span className="mono">{d.parentId}</span> remains in force.
                </>
              ) : (
                <>
                  Model <span className="mono">{d.candidateId}</span> improved on the new
                  task and lost no more than the agreed tolerance on any earlier one. It is
                  now the model in force.
                </>
              )}
            </p>
          </div>
        </header>

        {/* -- the per-task table: the heart of it ------------------------- */}
        <section className="gpsec">
          <h2 className="gpsec__title">Measured against every task the network knows</h2>
          <div className="gptable-wrap scroll-x--dark">
            <table className="gptable">
              <thead>
                <tr>
                  <th scope="col">Task</th>
                  <th scope="col">Benchmark</th>
                  <th scope="col">Sealed</th>
                  <th scope="col">{d.parentId}</th>
                  <th scope="col">{d.candidateId}</th>
                  <th scope="col">Change</th>
                  <th scope="col">Tolerance</th>
                  <th scope="col">Verdict</th>
                </tr>
              </thead>
              <tbody>
                {d.perTask.map((t) => (
                  <tr key={t.taskId} className={t.pass ? '' : 'is-fail'}>
                    <th scope="row">
                      {t.label}
                      {t.isNewTask && <span className="gptable__new stamp-type">new task</span>}
                    </th>
                    <td><HashChip value={t.benchmarkHash} dark /></td>
                    <td className="mono dim">{t.sealedAt.slice(0, 10)}</td>
                    <td className="mono">{bp(t.previousBp)}%</td>
                    <td className="mono">{bp(t.candidateBp)}%</td>
                    <td className={`mono ${t.pass ? 'ok' : 'bad'}`}>{bpDelta(t.changeBp)}</td>
                    <td className="mono dim">
                      {t.isNewTask ? `≥ +${bp(t.thresholdBp)}` : `≥ ${bp(t.thresholdBp)}`}
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
            Every benchmark hash above was committed to the ledger <em>before</em> this
            round opened, and revealed only after the decision. The organisations training
            in a round do not hold the set they will be judged against.
          </p>
        </section>

        {/* -- the rule ---------------------------------------------------- */}
        <section className="gpsec">
          <h2 className="gpsec__title">The rule the consortium agreed</h2>
          <div className="rules">
            <Rule label="Minimum gain on the new task" value={`+${bp(d.parameters.gammaBp)} points`} sym="γ" />
            <Rule label="Maximum loss on any earlier task" value={`${bp(d.parameters.tauBp)} points`} sym="τ" />
            <Rule label="Independent organisations required" value={`${d.parameters.k} of 5`} sym="k" />
            <Rule label="Tolerated disagreement between them" value={`${bp(d.parameters.deltaBp)} points`} sym="δ" />
          </div>
        </section>

        {/* -- who evaluated it -------------------------------------------- */}
        <section className="gpsec">
          <h2 className="gpsec__title">Who evaluated it, and what they signed</h2>
          <p className="small gpsec__lede">
            The contract does not run the model. It cannot: the weights are off-chain, and a
            floating-point forward pass is not identical across hardware. Each organisation
            evaluated the candidate itself and signed the accuracies it measured. The
            contract verified those certificates, checked the organisations agreed, and used
            the median.
          </p>
          <div className="endorsers">
            {d.endorsers.map((e) => (
              <div key={e.mspId} className="endorser">
                <div className="endorser__top">
                  <span className="endorser__org">{orgName(e.mspId)}</span>
                  <span className={`endorser__agree stamp-type ${e.agreed ? 'ok' : 'bad'}`}>
                    {e.agreed ? 'within δ' : 'disagreed'}
                  </span>
                </div>
                <p className="mono endorser__msp">{e.mspId}</p>
                <div className="endorser__foot">
                  <span className="mono endorser__bp">{bp(e.signedBp)}%</span>
                  <HashChip value={e.fingerprint} dark />
                </div>
              </div>
            ))}
          </div>
          <div className="median">
            <span className="stamp-type">Median used by the contract</span>
            <span className="mono median__v">
              {bp(d.perTask.find((t) => !t.pass || t.isNewTask)!.candidateBp)}%
            </span>
          </div>
        </section>

        {/* -- replay ------------------------------------------------------ */}
        <section className="gpsec">
          <h2 className="gpsec__title">Replay the decision</h2>
          <GateSimulator decision={d} compact />
        </section>

        {/* -- the ledger record ------------------------------------------- */}
        <section className="gpsec">
          <h2 className="gpsec__title">What was written to the ledger</h2>
          <div className="gprecord">
            <LedgerRow label="Outcome" dark>
              {rejected ? 'Rejected' : 'Promoted'} · <span className="mono">{d.reasonCode}</span>
            </LedgerRow>
            <LedgerRow label="Decided" dark>{dateTime(d.decidedAt)}</LedgerRow>
            <LedgerRow label="Candidate hash" dark><HashChip value={d.candidateHash} dark /></LedgerRow>
            <LedgerRow label="Parent model" dark><span className="mono">{d.parentId}</span></LedgerRow>
            <LedgerRow label="Memory bank" dark><HashChip value={d.memoryBankHash} dark /></LedgerRow>
            <LedgerRow label="Endorser set" dark>
              {d.endorsers.map((e) => e.mspId).join(', ')}
            </LedgerRow>
            <LedgerRow label="Transaction" dark><HashChip value={d.txId} dark /></LedgerRow>
            <LedgerRow label="Block" dark><span className="mono">#{commas(d.block)}</span></LedgerRow>
          </div>

          <div className="recompute">
            <ShieldCheck size={17} />
            <div>
              <p className="recompute__head">Verify this decision yourself</p>
              <p className="small recompute__body">
                Every input is on the ledger: the benchmark hashes, the signed metrics, the
                endorser set and the parameters. Any member can recompute this outcome and
                get the same answer.
              </p>
            </div>
            <button type="button" className="btn btn--onDark btn--sm">Recompute</button>
          </div>
        </section>
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
