import { ArrowUpRight, Plus } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Failed, Result } from '../components/states';
import { HashChip, Seal } from '../components/ui';
import {
  ApiError, api, recordLabel, shortMsp,
  type AccessRequest, type ActivityEvent, type Grant, type LedgerRecord,
} from '../lib/api';
import { commas, dateTime, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import './loom.css';

const STRIP = 12;

/**
 * The Loom Floor — the factory's dashboard.
 *
 * Its job is producing evidence. The work happens in shifts and is thought
 * about in periods, so this is not a grid of cards: it is a bolt of cloth
 * unrolling downward, newest at the top, with a shift log ruled down the side
 * like a workshop notebook.
 *
 * Everything on it is the ledger's. The shift log used to be seven sentences
 * written by hand; it is now the block log, which is the only account of what
 * happened that cannot be tidied up afterwards.
 */
export default function LoomFloor() {
  const { role } = useSession();
  const world = useApi(
    () => Promise.all([api.records(), api.grants(), api.activity(14), api.requests()]) as
      Promise<[LedgerRecord[], Grant[], ActivityEvent[], AccessRequest[]]>,
    [],
  );

  return (
    <div className="loomfloor">
      <Result query={world} pendingLabel="Reading your records off the chain">
        {([records, grants, activity, requests]) => {
          const sealed = records.filter((r) => r.status === 'committed');
          const active = grants.filter((g) => g.status === 'active');
          const pending = requests.filter((r) => r.status === 'pending');
          const revoked = grants.filter((g) => g.status === 'revoked');
          const recent = [...records]
            .sort((a, b) => b.committed_at.localeCompare(a.committed_at))
            .slice(0, STRIP);

          return (
            <>
              <header className="lf__head">
                <div>
                  <p className="stamp-type lf__eyebrow">
                    {role?.org} · {[...new Set(records.map((r) => r.site))].join(' · ') || '—'}
                  </p>
                  <h1>Good afternoon, {role?.person.split(' ')[0]}.</h1>
                  <p className="lead lf__lede">
                    {commas(sealed.length)} bolts sealed · {commas(active.length)} grants open
                    {pending.length > 0 && ` · ${pending.length} request awaiting you`}
                  </p>
                </div>
                {/* Both were figures with nothing behind them: a dashboard
                    counting revoked grants on a page that could not revoke one,
                    and no screen anywhere that listed either. */}
                <div className="lf__counts">
                  <Count
                    to="/factory/access"
                    n={pending.length}
                    label="awaiting your response"
                    tone={pending.length ? 'warn' : 'calm'}
                  />
                  <Count
                    to="/factory/access"
                    n={revoked.length}
                    label="grants you have revoked"
                    tone={revoked.length ? 'warn' : 'calm'}
                  />
                </div>
              </header>

              <div className="lf__body">
                <div className="strip">
                  <Link to="/factory/upload" className="onloom">
                    <div className="onloom__edge" aria-hidden="true" />
                    <div className="onloom__body">
                      <p className="stamp-type onloom__state">On the loom</p>
                      <h3>Seal a finished record</h3>
                      <p className="small onloom__note">
                        A finalised export — payroll, safety, chemical or maintenance. The
                        file stays here; only its root hash goes to the ledger.
                      </p>
                    </div>
                    <span className="onloom__go" aria-hidden="true"><Plus size={18} /></span>
                  </Link>

                  <p className="stamp-type strip__label">
                    Sealed · newest first · showing {recent.length} of {commas(records.length)}
                    {records.length > STRIP && (
                      <>
                        {' · '}
                        <Link to="/factory/records" className="strip__all">see all</Link>
                      </>
                    )}
                  </p>

                  {recent.map((b) => (
                    <Link
                      key={b.record_id}
                      to={`/factory/records/${encodeURIComponent(b.record_id)}`}
                      className={`bolt ${b.status === 'superseded' ? 'is-superseded' : ''}`}
                    >
                      <div className="bolt__selvedge" aria-hidden="true">
                        {Array.from({ length: 9 }, (_, i) => <span key={i} />)}
                      </div>
                      <div className="bolt__main">
                        <div className="bolt__top">
                          <h3 className="bolt__title">{recordLabel(b.record_type)}</h3>
                          <Seal tone={b.status === 'committed' ? 'sealed' : 'inert'}>
                            {b.status === 'committed' ? 'Sealed' : 'Superseded'}
                          </Seal>
                        </div>
                        <p className="bolt__meta small">
                          {period(b.period)} · {b.site} · schema {b.schema_version}
                        </p>
                        <div className="bolt__foot">
                          <span className="bolt__threads mono">
                            {commas(b.row_count)} threads
                          </span>
                          {b.witnesses.length > 0 && (
                            <span className="bolt__block mono">
                              witnessed by {b.witnesses.map(shortMsp).join(', ')}
                            </span>
                          )}
                          <HashChip value={b.merkle_root} />
                        </div>
                        {b.superseded_by && (
                          <p className="small bolt__note">
                            Replaced by {b.superseded_by}. It stays verifiable — a
                            correction is part of the history, not a replacement for it.
                          </p>
                        )}
                      </div>
                      <span className="bolt__date mono">{longDate(b.committed_at)}</span>
                    </Link>
                  ))}
                </div>

                <aside className="shiftlog">
                  <div className="shiftlog__head">
                    <p className="stamp-type">Shift log</p>
                    <Link to="/ledger" className="shiftlog__all">
                      ledger <ArrowUpRight size={12} />
                    </Link>
                  </div>
                  {activity.length === 0 ? (
                    <p className="small shiftlog__none">
                      Nothing on the chain from this organisation yet.
                    </p>
                  ) : (
                    <ol className="shiftlog__list">
                      {activity.map((e) => (
                        <li key={e.tx_id} className={`logline logline--${e.kind}`}>
                          <span className="mono logline__at">{dateTime(e.at).split(' · ')[0]}</span>
                          <span className="logline__text">
                            {e.text}
                            <span className="dim"> · block #{commas(e.block)}</span>
                          </span>
                        </li>
                      ))}
                    </ol>
                  )}

                  <Inbox
                    requests={pending}
                    records={records}
                    onDone={world.reload}
                  />
                </aside>
              </div>
            </>
          );
        }}
      </Result>
    </div>
  );
}

/**
 * The requests waiting on a decision.
 *
 * Granting names a record, because a request asks about a period and a grant is
 * about a document. The contract decides whether the grant is allowed; this
 * form only carries the question to it.
 */
function Inbox({
  requests, records, onDone,
}: {
  requests: AccessRequest[];
  records: LedgerRecord[];
  onDone: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const [chosen, setChosen] = useState<Record<string, string>>({});

  const act = async (id: string, fn: () => Promise<unknown>) => {
    setBusy(id);
    setFailure(null);
    try {
      await fn();
      onDone();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'that did not work'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="shiftlog__requests">
      <div className="shiftlog__head">
        <p className="stamp-type">Awaiting you</p>
        <Link to="/factory/access" className="shiftlog__all">
          access <ArrowUpRight size={12} />
        </Link>
      </div>
      {failure && <Failed error={failure} />}
      {requests.length === 0 ? (
        <p className="small shiftlog__none">Nothing waiting.</p>
      ) : (
        requests.map((r) => {
          const candidates = records.filter(
            (x) => x.record_type === r.record_type && x.period === r.period,
          );
          const pick = chosen[r.id] ?? candidates[0]?.record_id ?? '';
          return (
            <div key={r.id} className="req">
              <p className="req__who">{shortMsp(r.requester_msp)}</p>
              <p className="small req__what">
                wants <span className="mono">{r.field_name}</span> from{' '}
                {recordLabel(r.record_type)}, {period(r.period)}
              </p>
              {candidates.length === 0 ? (
                <p className="small req__what dim">
                  No record of that type and period is on the ledger, so there is nothing
                  to grant against.
                </p>
              ) : (
                <label className="req__pick">
                  <span className="stamp-type">Grant against</span>
                  <select
                    className="input"
                    value={pick}
                    onChange={(e) => setChosen({ ...chosen, [r.id]: e.target.value })}
                  >
                    {candidates.map((c) => (
                      <option key={c.record_id} value={c.record_id}>
                        {c.record_id} · {c.site} · {commas(c.row_count)} rows
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <div className="req__actions">
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  disabled={busy === r.id || !pick}
                  onClick={() => act(r.id, () => api.answerRequest(r.id, pick))}
                >
                  {busy === r.id ? 'Writing…' : 'Grant one field'}
                </button>
                {/* Declining asks for a reason, and a reason wants more room
                    than a sidebar column has. The buyer is told why, so this is
                    not a refusal that can be fired off by accident. */}
                <Link to="/factory/access" className="btn btn--ghost btn--sm">
                  Decline…
                </Link>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

function Count({
  n, label, tone, to,
}: { n: number; label: string; tone: 'warn' | 'calm'; to: string }) {
  return (
    <Link to={to} className={`count count--${tone}`}>
      <span className="count__n">{n}</span>
      <span className="small count__l">{label}</span>
    </Link>
  );
}
