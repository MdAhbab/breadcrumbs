import { ArrowUpRight, Plus } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Failed, Result } from '../components/states';
import { Tech } from '../components/Tech';
import { HashChip, Seal } from '../components/ui';
import {
  ApiError, api, recordLabel, shortMsp,
  type AccessRequest, type ActivityEvent, type Grant, type LedgerRecord,
} from '../lib/api';
import { commas, dateTime, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import { useFieldLabel } from '../lib/useFieldLabel';
import './loom.css';

const STRIP = 12;

/**
 * The factory's overview.
 *
 * Its job is producing evidence, so the page is a list of what has been
 * published, newest first, with the ledger's own account of recent activity
 * down the side.
 *
 * It opens with the one thing this person is here to decide — whoever is
 * waiting on an answer from them — because a dashboard that only reports is a
 * dashboard the reader has to work out the next move from.
 *
 * Everything on it is the ledger's. The activity column is the block log, which
 * is the only account of what happened that cannot be tidied up afterwards.
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
                    {role?.org} · {[...new Set(records.map((r) => r.site))].join(' · ') || 'no site yet'}
                  </p>
                  <h1>Good afternoon, {role?.person.split(' ')[0]}.</h1>
                  <p className="lead lf__lede">
                    {commas(sealed.length)} records published · {commas(active.length)} people
                    currently allowed to see something
                  </p>
                </div>
                {/* Both were figures with nothing behind them: a dashboard
                    counting revoked grants on a page that could not revoke one,
                    and no screen anywhere that listed either. */}
                <div className="lf__counts">
                  <Count
                    to="/factory/access"
                    n={pending.length}
                    label="requests waiting on you"
                    tone={pending.length ? 'warn' : 'calm'}
                  />
                  <Count
                    to="/factory/access"
                    n={revoked.length}
                    label="permissions you withdrew"
                    tone={revoked.length ? 'warn' : 'calm'}
                  />
                </div>
              </header>

              <div className="lf__body">
                <div className="strip">
                  <Link to="/factory/upload" className="onloom">
                    <div className="onloom__edge" aria-hidden="true" />
                    <div className="onloom__body">
                      <p className="stamp-type onloom__state">Start here</p>
                      <h3>Publish a finished record</h3>
                      <p className="small onloom__note">
                        A finished export: payroll, safety, chemicals or maintenance. The
                        file stays on your machine. Only a fingerprint of it goes to the
                        ledger, which is enough to prove it later and not enough to read it.
                      </p>
                    </div>
                    <span className="onloom__go" aria-hidden="true"><Plus size={18} /></span>
                  </Link>

                  <p className="stamp-type strip__label">
                    Published · newest first · showing {recent.length} of {commas(records.length)}
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
                            {b.status === 'committed' ? 'Published' : 'Corrected'}
                          </Seal>
                        </div>
                        <p className="bolt__meta small">
                          {period(b.period)} · {b.site}
                          <Tech> · schema {b.schema_version}</Tech>
                        </p>
                        <div className="bolt__foot">
                          <span className="bolt__threads">
                            {commas(b.row_count)} rows
                          </span>
                          {b.witnesses.length > 0 && (
                            <span className="bolt__block">
                              checked by {b.witnesses.map(shortMsp).join(', ')}
                            </span>
                          )}
                          <Tech><HashChip value={b.merkle_root} /></Tech>
                        </div>
                        {b.superseded_by && (
                          <p className="small bolt__note">
                            Corrected by a later version. This one can still be checked.
                            A correction is added to the history, it does not replace it.
                          </p>
                        )}
                      </div>
                      <span className="bolt__date mono">{longDate(b.committed_at)}</span>
                    </Link>
                  ))}
                </div>

                <aside className="shiftlog">
                  <div className="shiftlog__head">
                    <p className="stamp-type">Recent activity</p>
                    <Link to="/ledger" className="shiftlog__all">
                      all of it <ArrowUpRight size={12} />
                    </Link>
                  </div>
                  {activity.length === 0 ? (
                    <p className="small shiftlog__none">
                      Nothing from your organisation on the ledger yet.
                    </p>
                  ) : (
                    <ol className="shiftlog__list">
                      {activity.map((e) => (
                        <li key={e.tx_id} className={`logline logline--${e.kind}`}>
                          <span className="mono logline__at">{dateTime(e.at).split(' · ')[0]}</span>
                          <span className="logline__text">
                            {e.text}
                            <Tech><span className="dim"> · block #{commas(e.block)}</span></Tech>
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
 * Approving names a record, because a request asks about a month and an
 * approval is about one document. The contract decides whether it is allowed;
 * this form only carries the question to it.
 */
function Inbox({
  requests, records, onDone,
}: {
  requests: AccessRequest[];
  records: LedgerRecord[];
  onDone: () => void;
}) {
  const labelOf = useFieldLabel();
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
        <p className="stamp-type">Waiting on you</p>
        <Link to="/factory/access" className="shiftlog__all">
          all requests <ArrowUpRight size={12} />
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
                wants <strong>{labelOf(r.record_type, r.field_name)}</strong> from{' '}
                {recordLabel(r.record_type)}, {period(r.period)}
              </p>
              {candidates.length === 0 ? (
                <p className="small req__what dim">
                  You have not published a record of that kind for that month, so there
                  is nothing to give them yet.
                </p>
              ) : (
                <label className="req__pick">
                  <span className="stamp-type">Which record</span>
                  <select
                    className="input"
                    value={pick}
                    onChange={(e) => setChosen({ ...chosen, [r.id]: e.target.value })}
                  >
                    {candidates.map((c) => (
                      <option key={c.record_id} value={c.record_id}>
                        {c.site} · {commas(c.row_count)} rows · published{' '}
                        {longDate(c.committed_at)}
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
                  {busy === r.id ? 'Writing…' : 'Approve one field'}
                </button>
                {/* Refusing asks for a reason, and a reason wants more room
                    than a sidebar column has. The buyer is told why, so this is
                    not a refusal that can be fired off by accident. */}
                <Link to="/factory/access" className="btn btn--ghost btn--sm">
                  Refuse…
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
