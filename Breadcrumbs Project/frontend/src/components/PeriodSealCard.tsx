import { FileStack, History } from 'lucide-react';

import type { PeriodSeal } from '../lib/api';
import { longDate } from '../lib/format';
import { Tech } from './Tech';
import { HashChip, Seal } from './ui';
import './mechanisms.css';

/**
 * One closed reporting period.
 *
 * The count and the root are the seal. The amendment history is the part worth
 * designing carefully: a period reopened four times is telling you something
 * about the factory whether or not anybody meant it to, so the amendment count
 * is given the same weight as the seal itself rather than being folded away in
 * a detail panel.
 */
export function PeriodSealCard({ seal }: { seal: PeriodSeal }) {
  const amended = seal.amendments.length;

  return (
    <article className={`pseal ${amended ? 'is-amended' : ''}`}>
      <header className="pseal__head">
        <div>
          <p className="stamp-type pseal__eyebrow">
            {seal.record_type.replace(/_/g, ' ')} · {seal.site}
          </p>
          <h3 className="pseal__period">{seal.period}</h3>
        </div>
        {amended ? (
          <Seal tone="pending">
            amended {amended} {amended === 1 ? 'time' : 'times'}
          </Seal>
        ) : (
          <Seal tone="sealed">sealed</Seal>
        )}
      </header>

      <div className="pseal__figures">
        <div className="pseal__fig">
          <FileStack size={15} />
          <span className="pseal__n">{seal.record_count}</span>
          <span className="small">records this month is fixed at</span>
        </div>
        <div className="pseal__fig">
          <History size={15} />
          <span className="pseal__n">v{seal.version}</span>
          <span className="small">current version</span>
        </div>
      </div>

      <Tech>
        <div className="pseal__row">
          <span className="stamp-type">Records root</span>
          <HashChip value={seal.records_root} />
        </div>
      </Tech>
      <div className="pseal__row">
        <span className="stamp-type">Closed</span>
        <span className="small">{longDate(seal.sealed_at)} by {seal.sealed_by}</span>
      </div>

      {amended > 0 && (
        <div className="pseal__history">
          <p className="stamp-type pseal__histhead">Corrections since</p>
          <ol className="amends">
            {seal.amendments.map((a) => (
              <li key={a.version} className="amend">
                <span className="amend__mark" aria-hidden="true" />
                <div className="amend__body">
                  <p className="amend__reason">{a.reason}</p>
                  <p className="small amend__meta">
                    v{a.version} → v{a.version + 1} · {longDate(a.amended_at)} ·{' '}
                    {a.amended_by} · added {a.added.join(', ')}
                  </p>
                  <div className="amend__was">
                    <span className="stamp-type">was</span>
                    <span className="mono">{a.previous_count} records</span>
                    <Tech><HashChip value={a.previous_root} /></Tech>
                  </div>
                </div>
              </li>
            ))}
          </ol>
          <p className="small pseal__note">
            A correction is not an edit. What the month said before stays here
            permanently. That is what makes a factory correcting itself over and over
            impossible to hide.
          </p>
        </div>
      )}
    </article>
  );
}
