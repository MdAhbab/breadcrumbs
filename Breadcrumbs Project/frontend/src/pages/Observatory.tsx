import { Eye } from 'lucide-react';
import { useState } from 'react';

import { Failed, Result } from '../components/states';
import { Tech } from '../components/Tech';
import { Frosted, Seal } from '../components/ui';
import { ApiError, api, type RegulatorOverview, type Sla } from '../lib/api';
import { commas, longDate } from '../lib/format';
import { channelLabel } from '../lib/plainReason';
import { useApi } from '../lib/useApi';
import './observatory.css';

/**
 * The regulator's dashboard: votes, totals, and whether anything was altered.
 *
 * What the regulator may not see stays on the page behind glass, with the
 * reason on it, so the boundary is visible rather than silently missing. The
 * panels really call the endpoints they describe and show the server's refusal.
 */
export default function Observatory() {
  const world = useApi(
    () => Promise.all([api.regulatorOverview(), api.sla()]) as
      Promise<[RegulatorOverview, Sla]>,
    [],
  );

  return (
    <div className="obs">
      <div className="obs__condition grain">
        <Eye size={16} />
        <div>
          <p className="obs__condition-head">Read-only access</p>
          <p className="small obs__condition-body">
            You can see totals and votes. You cannot change anything.
          </p>
        </div>
      </div>

      <Result query={world} pendingLabel="Reading what you may see">
        {([overview, sla]) => (
          <>
            <header className="obs__head">
              <p className="stamp-type obs__eyebrow">Dept. of Labour, Bangladesh</p>
              <h1>Dashboard</h1>
              <p className="lead obs__lede">
                Votes, totals, and whether anything on the ledger was altered.
              </p>
            </header>

            <section className="obs__section">
              <p className="stamp-type obs__label">Visible to you</p>
              <div className="figures">
                <Figure n={commas(overview.kpis.active_factories)} label="active factories" />
                <Figure n={commas(overview.kpis.total_organisations)} label="members" />
                <Figure n={commas(overview.kpis.open_proposals)} label="votes open" />
                <Figure n={commas(sla.kpis.total_verifications)} label="checks recorded" />
                <Figure
                  n={commas(overview.chain.reduce((a, c) => a + c.height, 0))}
                  label="entries on the ledger"
                />
                <Figure
                  n={overview.chain.every((c) => c.integrity_ok) ? 'Nothing' : 'Something'}
                  label="altered on the ledger"
                />
              </div>
            </section>

            <section className="obs__section">
              <p className="stamp-type obs__label">Votes</p>
              {overview.governance_events.length === 0 ? (
                <p className="small obs__explain">Nothing has been put to a vote.</p>
              ) : (
                <ol className="events">
                  {overview.governance_events.map((e, i) => (
                    <li key={i} className="event">
                      <span className="event__body">
                        <span className="event__title">{e.title}</span>
                        <span className="small event__meta">
                          {e.kind.replace(/_/g, ' ')} · opened {longDate(e.opened_at)} · {e.org}
                        </span>
                      </span>
                      <Seal tone={e.status === 'approved' ? 'sealed' : 'pending'}>
                        {e.status === 'approved' ? 'Approved'
                          : e.status === 'pending' ? 'Waiting' : e.status}
                      </Seal>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <section className="obs__section">
              <p className="stamp-type obs__label">The ledger</p>
              <table className="ghosttable ghosttable--ledger">
                <thead>
                  <tr>
                    <th scope="col">Holds</th>
                    <th scope="col" className="num">Entries</th>
                    <th scope="col" className="num">Members</th>
                    <th scope="col">Altered?</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.chain.map((c) => (
                    <tr key={c.channel}>
                      <td>
                        {channelLabel(c.channel)}
                        <Tech><span className="mono small dim ghosttable__raw">{c.channel}</span></Tech>
                      </td>
                      <td className="mono num">{commas(c.height)}</td>
                      <td className="mono num">{commas(c.members.length)}</td>
                      <td>
                        <Seal tone={c.integrity_ok ? 'sealed' : 'broken'}>
                          {c.integrity_ok ? 'No' : 'Yes'}
                        </Seal>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section className="obs__section">
              <p className="stamp-type obs__label obs__label--closed">
                Present, but closed to you
              </p>
              <p className="small obs__explain">
                These hold data you cannot open. The server refuses, not just this screen.
              </p>

              <div className="obs__closed">
                <Refused
                  title="Factory documents"
                  call={() => api.records()}
                  fallback="Factory documents need a separate legal permission."
                />
                <Refused
                  title="Closed months"
                  call={() => api.seals()}
                  fallback="A closed month is about one named factory."
                />
                <Refused
                  title="Permissions"
                  call={() => api.grants()}
                  fallback="Permissions name the buyers involved."
                />
              </div>

              <div className="obs__request">
                <p className="small">
                  To get access, the members must vote on it. The request and the vote both
                  go on the ledger.
                </p>
              </div>
            </section>
          </>
        )}
      </Result>
    </div>
  );
}

/**
 * A panel that shows its own refusal.
 *
 * It calls the endpoint on demand and prints whatever comes back. If the
 * capability table ever changed so that this role could read one of these, the
 * panel would fill with data rather than continuing to claim a boundary that no
 * longer existed.
 */
function Refused({
  title, call, fallback,
}: {
  title: string;
  call: () => Promise<unknown>;
  fallback: string;
}) {
  const [result, setResult] = useState<'idle' | 'denied' | 'open'>('idle');
  const [error, setError] = useState<ApiError | null>(null);
  const [rows, setRows] = useState<number>(0);

  const attempt = async () => {
    try {
      const data = await call();
      setRows(Array.isArray(data) ? data.length : 1);
      setResult('open');
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, fallback));
      setResult('denied');
    }
  };

  return (
    <Frosted reason={error?.message ?? fallback}>
      <div className="ghost">
        <p className="stamp-type ghost__head">{title}</p>
        {result === 'idle' && (
          <button type="button" className="btn btn--ghost btn--sm" onClick={() => void attempt()}>
            Try to open it
          </button>
        )}
        {result === 'denied' && error && <Failed error={error} />}
        {result === 'open' && (
          <p className="small">
            The server sent {commas(rows)} row{rows === 1 ? '' : 's'}. This is no longer
            closed to you.
          </p>
        )}
      </div>
    </Frosted>
  );
}

function Figure({ n, label }: { n: number | string; label: string }) {
  return (
    <div className="figure">
      <span className="figure__n">{n}</span>
      <span className="small figure__l">{label}</span>
    </div>
  );
}
