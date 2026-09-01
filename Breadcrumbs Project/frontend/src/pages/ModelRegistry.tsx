import { Link } from 'react-router-dom';

import { HashChip, Seal } from '../components/ui';
import { REGISTRY } from '../lib/data';
import { bp, longDate } from '../lib/format';
import './registry.css';

const TASKS = ['Wage register', 'Certificates', 'Chemical'];

/**
 * Model lineage.
 *
 * Rejected versions stay in the list, with the reason they were refused. A
 * registry that shows only what shipped cannot answer the question an auditor
 * actually asks — what did you try, and why was it turned down?
 */
export default function ModelRegistry() {
  return (
    <div className="reg">
      <header className="reg__head">
        <p className="stamp-type reg__eyebrow">Model channel · lineage</p>
        <h1>Every version, promoted and refused.</h1>
        <p className="lead reg__lede">
          Each candidate was judged against benchmarks sealed before its round opened. The
          refusals are the interesting half of this list.
        </p>
      </header>

      <ol className="lineage">
        {REGISTRY.map((m) => (
          <li key={m.modelId} className={`ver is-${m.status}`}>
            <div className="ver__spine" aria-hidden="true">
              <span className="ver__node" />
            </div>

            <div className="ver__body">
              <div className="ver__top">
                <span className="mono ver__id">{m.modelId}</span>
                <Seal
                  tone={
                    m.status === 'in_force' ? 'sealed'
                      : m.status === 'promoted' ? 'sealed'
                        : m.status === 'rejected' ? 'broken' : 'inert'
                  }
                >
                  {m.status.replace('_', ' ')}
                </Seal>
                <span className="small ver__date">{longDate(m.decidedAt)}</span>
              </div>

              <p className="ver__reason">{m.reason}</p>

              <div className="ver__acc">
                {m.accuracies.map((a, i) => (
                  <span key={i} className="acc">
                    <span className="stamp-type acc__t">{TASKS[i]}</span>
                    <span className="mono acc__v">{bp(a)}%</span>
                    <span className="acc__bar" aria-hidden="true">
                      <span style={{ width: `${a / 100}%` }} />
                    </span>
                  </span>
                ))}
              </div>

              <div className="ver__foot">
                <span className="small ver__meta">
                  parent <span className="mono">{m.parentId ?? '—'}</span> ·{' '}
                  {m.contributors} contributors
                </span>
                <HashChip value={m.memoryBankHash} />
                <Link to={`/model/gate/${m.modelId}`} className="ver__link">
                  the decision →
                </Link>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
