import { ArrowUpRight, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';

import { HashChip, Seal } from '../components/ui';
import { BOLTS, GRANTS, RECORD_LABEL, SHIFT_LOG, orgName } from '../lib/data';
import { commas, longDate, period } from '../lib/format';
import './loom.css';

/**
 * The Loom Floor — Fatema's dashboard.
 *
 * Her job is producing evidence. She works in shifts and thinks in periods, so
 * this is not a grid of cards: it is a bolt of cloth unrolling downward, newest
 * at the top, with a shift log ruled down the side like a workshop notebook.
 *
 * The one thing she does most — sealing a record — is never more than one click
 * away, and it sits at the head of the strip in an "on the loom" state rather
 * than as a button floating in a header.
 */
export default function LoomFloor() {
  const pending = GRANTS.filter((g) => g.status === 'pending');
  const active = GRANTS.filter((g) => g.status === 'active');
  const expiring = active.filter((g) => new Date(g.expiresAt) < new Date('2026-10-01'));

  return (
    <div className="loomfloor">
      <header className="lf__head">
        <div>
          <p className="stamp-type lf__eyebrow">Apex Textile Ltd · Gazipur</p>
          <h1>Good afternoon, Fatema.</h1>
          <p className="lead lf__lede">
            {BOLTS.filter((b) => b.status === 'committed').length} bolts sealed ·{' '}
            {active.length} grants open · {pending.length} request awaiting you
          </p>
        </div>
        <div className="lf__counts">
          <Count n={pending.length} label="awaiting your response" tone={pending.length ? 'warn' : 'calm'} />
          <Count n={expiring.length} label="expiring within 30 days" tone={expiring.length ? 'warn' : 'calm'} />
        </div>
      </header>

      <div className="lf__body">
        {/* ------------------------------------------------- the bolt strip */}
        <div className="strip">
          {/* on the loom */}
          <Link to="/factory/upload" className="onloom">
            <div className="onloom__edge" aria-hidden="true" />
            <div className="onloom__body">
              <p className="stamp-type onloom__state">On the loom</p>
              <h3>Seal a finished record</h3>
              <p className="small onloom__note">
                A finalised export — payroll, safety, chemical or maintenance. The file
                stays here; only its root hash goes to the ledger.
              </p>
            </div>
            <span className="onloom__go" aria-hidden="true"><Plus size={18} /></span>
          </Link>

          <p className="stamp-type strip__label">Sealed · newest first</p>

          {BOLTS.map((b) => (
            <Link
              key={b.recordId}
              to={`/factory/records/${b.recordId}`}
              className={`bolt ${b.status === 'superseded' ? 'is-superseded' : ''}`}
            >
              <div className="bolt__selvedge" aria-hidden="true">
                {Array.from({ length: 9 }, (_, i) => <span key={i} />)}
              </div>
              <div className="bolt__main">
                <div className="bolt__top">
                  <h3 className="bolt__title">{RECORD_LABEL[b.recordType]}</h3>
                  <Seal tone={b.status === 'committed' ? 'sealed' : 'inert'}>
                    {b.status === 'committed' ? 'Sealed' : 'Superseded'}
                  </Seal>
                </div>
                <p className="bolt__meta small">
                  {period(b.period)} · {b.site} · schema {b.schemaVersion}
                </p>
                <div className="bolt__foot">
                  <span className="bolt__threads mono">{commas(b.rowCount)} threads</span>
                  <span className="bolt__block mono">block #{commas(b.block)}</span>
                  <HashChip value={b.merkleRoot} />
                </div>
                {b.supersededBy && (
                  <p className="small bolt__note">
                    Replaced by {b.supersededBy} after an overtime recalculation. It stays
                    verifiable — a correction is part of the history, not a replacement
                    for it.
                  </p>
                )}
              </div>
              <span className="bolt__date mono">{longDate(b.committedAt)}</span>
            </Link>
          ))}
        </div>

        {/* ------------------------------------------------- the shift log */}
        <aside className="shiftlog">
          <div className="shiftlog__head">
            <p className="stamp-type">Shift log</p>
            <Link to="/ledger" className="shiftlog__all">
              ledger <ArrowUpRight size={12} />
            </Link>
          </div>
          <ol className="shiftlog__list">
            {SHIFT_LOG.map((e, i) => (
              <li key={i} className={`logline logline--${e.kind}`}>
                <span className="mono logline__at">{e.at}</span>
                <span className="logline__text">{e.text}</span>
              </li>
            ))}
          </ol>

          <div className="shiftlog__requests">
            <p className="stamp-type">Awaiting you</p>
            {pending.length === 0 ? (
              <p className="small shiftlog__none">Nothing waiting.</p>
            ) : (
              pending.map((g) => (
                <div key={g.grantId} className="req">
                  <p className="req__who">{orgName(g.requesterMsp)}</p>
                  <p className="small req__what">
                    wants <span className="mono">{g.fieldName}</span> from{' '}
                    {period(g.recordId === 'rc-004' ? '2026-08' : '2026-07')}
                  </p>
                  <div className="req__actions">
                    <button type="button" className="btn btn--primary btn--sm">Grant one field</button>
                    <button type="button" className="btn btn--ghost btn--sm">Decline</button>
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Count({ n, label, tone }: { n: number; label: string; tone: 'warn' | 'calm' }) {
  return (
    <div className={`count count--${tone}`}>
      <span className="count__n">{n}</span>
      <span className="small count__l">{label}</span>
    </div>
  );
}
