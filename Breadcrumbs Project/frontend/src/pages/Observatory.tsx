import { Eye } from 'lucide-react';
import { useState } from 'react';

import { Failed, Result } from '../components/states';
import { Frosted, Seal } from '../components/ui';
import { ApiError, api, type RegulatorOverview, type Sla } from '../lib/api';
import { commas, longDate } from '../lib/format';
import { useApi } from '../lib/useApi';
import './observatory.css';

/**
 * The Observatory — the regulator's view.
 *
 * The most interesting design problem in the product, because a regulator's
 * defining characteristic is what they may *not* see.
 *
 * Most software treats permissions as absence: it hides what you cannot access,
 * and you learn nothing. Here the restricted regions stay on the page behind
 * glass — the shape of the data is visible, the content is not, and the exact
 * lawful basis required is stated on each one. Absence teaches nothing; a drawn
 * boundary teaches the rule.
 *
 * The glass now covers a real refusal. The panels below actually call the
 * endpoints they describe, and what they show is the 403 the server returned,
 * with the capability table's own sentence. The previous version drew frosted
 * glass over a copy of the factory's records held in the frontend — the one
 * screen in the product whose entire subject is a boundary was rendering data
 * from the far side of it.
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
          <p className="obs__condition-head">Read-only observer access</p>
          <p className="small obs__condition-body">
            You are seeing aggregate governance statistics and events. Factory-level
            records and personal data require a separate lawful-basis access grant.
          </p>
        </div>
      </div>

      <Result query={world} pendingLabel="Reading what you are permitted">
        {([overview, sla]) => (
          <>
            <header className="obs__head">
              <p className="stamp-type obs__eyebrow">Dept. of Labour, Bangladesh</p>
              <h1>Observatory</h1>
            </header>

            <section className="obs__section">
              <p className="stamp-type obs__label">Visible to you</p>
              <div className="figures">
                <Figure n={overview.kpis.active_factories} label="active factories" />
                <Figure n={overview.kpis.total_organisations} label="organisations in the consortium" />
                <Figure n={overview.kpis.open_proposals} label="motions open" />
                <Figure n={commas(sla.kpis.total_verifications)} label="verifications recorded" />
                <Figure
                  n={overview.chain.reduce((a, c) => a + c.height, 0)}
                  label="blocks across all channels"
                />
                <Figure
                  n={overview.chain.every((c) => c.integrity_ok) ? 'passing' : 'FAILING'}
                  label="chain integrity re-check"
                />
              </div>
              <p className="small obs__explain">
                {sla.unmeasured.reason}
              </p>
            </section>

            <section className="obs__section">
              <p className="stamp-type obs__label">Governance events</p>
              {overview.governance_events.length === 0 ? (
                <p className="small obs__explain">No motions have been opened.</p>
              ) : (
                <ol className="events">
                  {overview.governance_events.map((e, i) => (
                    <li key={i} className="event">
                      <span className="mono event__case">{String(i + 1).padStart(3, '0')}</span>
                      <span className="event__body">
                        <span className="event__title">{e.title}</span>
                        <span className="small event__meta">
                          {e.kind.replace(/_/g, ' ')} · opened {longDate(e.opened_at)} · {e.org}
                        </span>
                      </span>
                      <Seal tone={e.status === 'approved' ? 'sealed' : 'pending'}>
                        {e.status}
                      </Seal>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <section className="obs__section">
              <p className="stamp-type obs__label">Channels</p>
              <div className="scroll-x">
                <table className="ghosttable">
                  <thead>
                    <tr>
                      <th scope="col">Channel</th>
                      <th scope="col">Height</th>
                      <th scope="col">Members</th>
                      <th scope="col">Integrity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.chain.map((c) => (
                      <tr key={c.channel}>
                        <td className="mono">{c.channel}</td>
                        <td className="mono">{commas(c.height)}</td>
                        <td>{c.members.length}</td>
                        <td>
                          <Seal tone={c.integrity_ok ? 'sealed' : 'broken'}>
                            {c.integrity_ok ? 'verified' : 'failed'}
                          </Seal>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="obs__section">
              <p className="stamp-type obs__label obs__label--closed">
                Present, but closed to you
              </p>
              <p className="small obs__explain">
                These views exist and hold data. Your role does not carry the capability
                to read them, and the server refuses the request — not merely the
                interface. Each panel below made the call.
              </p>

              <div className="obs__closed">
                <Refused
                  title="Committed records"
                  call={() => api.records()}
                  fallback="Factory records require a separate lawful-basis access grant."
                />
                <Refused
                  title="Period seals"
                  call={() => api.seals()}
                  fallback="A seal is a statement about a named factory's bookkeeping."
                />
                <Refused
                  title="Access grants"
                  call={() => api.grants()}
                  fallback="Grant-level detail names individual counterparties and is out of scope."
                />
              </div>

              <div className="obs__request">
                <p className="small">
                  A lawful-basis grant is itself a motion of the consortium chamber,
                  recorded on the ledger like any other. Requesting one leaves a trail;
                  so does approving it.
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
            The server returned {rows} row{rows === 1 ? '' : 's'}. The capability table
            no longer refuses this role — the boundary this panel describes is gone.
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
