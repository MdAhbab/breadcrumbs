import { useState } from 'react';

import { ConsortiumMesh } from '../components/ConsortiumMesh';
import { Failed, Result } from '../components/states';
import { Tech } from '../components/Tech';
import { ApiError, api, shortMsp, type Org, type Proposal } from '../lib/api';
import { commas, longDate } from '../lib/format';
import { channelLabel } from '../lib/plainReason';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import './chamber.css';

/**
 * Members & voting — the consortium administrator's console.
 *
 * Proposals are set as readable prose, and each vote shows as a seal
 * impression rather than a progress bar. When a proposal is approved, a stamp
 * lands on it. Agreeing writes to the server, not to local state.
 */
export default function Chamber() {
  const { role } = useSession();
  const [tab, setTab] = useState<'motions' | 'network' | 'register'>('motions');
  const world = useApi(
    () => Promise.all([api.proposals(), api.orgs()]) as Promise<[Proposal[], Org[]]>,
    [],
  );

  return (
    <div className="chamber">
      <Result query={world} pendingLabel="Reading the votes">
        {([motions, orgs]) => (
          <>
            <header className="ch__head">
              <div>
                <p className="stamp-type ch__eyebrow">{role?.org}</p>
                <h1>Members &amp; voting</h1>
                <p className="lead ch__lede">
                  {commas(motions.filter((m) => m.status === 'pending').length)} votes open ·{' '}
                  {commas(orgs.length)} members
                </p>
              </div>
              <div className="ch__tabs" role="tablist">
                {(['motions', 'network', 'register'] as const).map((t) => (
                  <button
                    key={t}
                    role="tab"
                    aria-selected={tab === t}
                    className={`ch__tab ${tab === t ? 'is-on' : ''}`}
                    onClick={() => setTab(t)}
                  >
                    {{ motions: 'Votes', network: 'Who is connected', register: 'Members' }[t]}
                  </button>
                ))}
              </div>
            </header>

            {tab === 'network' && <ConsortiumMesh />}

            {tab === 'motions' && (
              <ol className="docket">
                {motions.map((m, i) => (
                  <Motion
                    key={m.id}
                    motion={m}
                    index={i}
                    mspId={role?.mspId ?? ''}
                    onEndorsed={world.reload}
                  />
                ))}
              </ol>
            )}

            {tab === 'register' && (
              <div className="register">
                <div className="scroll-x">
                  <table className="regtable">
                    <thead>
                      <tr>
                        <th scope="col">Organisation</th>
                        <Tech><th scope="col">Network identity</th></Tech>
                        <th scope="col">Role</th>
                        <th scope="col">Country</th>
                        <th scope="col">Can see</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orgs.map((o) => (
                        <tr key={o.msp_id}>
                          <th scope="row">
                            {o.name}
                            {o.is_you && <span className="small dim"> · you</span>}
                          </th>
                          <Tech><td className="mono">{o.msp_id}</td></Tech>
                          <td className="regtable__role">{o.kind_label}</td>
                          <td>{o.country}</td>
                          <td className="mono dim">
                            {o.channels.length === 0
                              ? 'nothing'
                              : o.channels.map(channelLabel).join(', ')}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="small register__note">
                  Adding or suspending a member takes a vote. Whoever runs the servers
                  cannot do it alone.
                </p>
              </div>
            )}
          </>
        )}
      </Result>
    </div>
  );
}

function Motion({
  motion: m, index, mspId, onEndorsed,
}: {
  motion: Proposal;
  index: number;
  mspId: string;
  onEndorsed: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const carried = m.threshold_reached;
  const mine = m.endorsers.includes(mspId);

  const endorse = async () => {
    setBusy(true);
    setFailure(null);
    try {
      await api.endorse(m.id);
      onEndorsed();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'your vote was not recorded'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={`motion ${carried ? 'is-carried' : ''}`}>
      <div className="motion__margin">
        <Tech>
          <p className="mono motion__case">
            BGMEA/M-{String(index + 41).padStart(3, '0')} · {m.id}
          </p>
        </Tech>
        <p className="stamp-type motion__kind">{m.kind.replace(/_/g, ' ')}</p>
        <p className="small motion__dates">
          opened {longDate(m.opened_at)}
          <br />
          {carried ? 'decided' : `closes ${longDate(m.closes_at)}`}
        </p>
      </div>

      <div className="motion__body">
        <h2 className="motion__title">{m.title}</h2>
        <p className="motion__prose">{m.body}</p>

        {/* Votes as impressions rather than a progress bar: it is a count of
            named organisations, not a percentage of something. */}
        <div className="seals">
          <p className="stamp-type seals__label">
            {commas(m.endorsement_count)} of {commas(m.required)} members have agreed
          </p>
          <div className="seals__row">
            {Array.from({ length: m.required }, (_, i) => {
              const org = m.endorsers[i];
              return (
                <span
                  key={i}
                  className={`impression ${org ? 'is-filled' : ''}`}
                  title={org ?? 'has not voted yet'}
                >
                  {org ? org.replace('MSP', '').slice(0, 2).toUpperCase() : ''}
                </span>
              );
            })}
          </div>
          <p className="small seals__who">
            {m.endorsers.length
              ? m.endorsers.map(shortMsp).join(' · ')
              : 'Nobody has agreed yet.'}
          </p>
        </div>

        {failure && <Failed error={failure} />}

        {carried ? (
          <div className="carried">
            <span className="carried__stamp stamp-type">Approved</span>
            <p className="small carried__note">
              Enough members agreed. The vote is on the ledger and cannot be changed.
            </p>
          </div>
        ) : (
          <div className="motion__actions">
            <button
              type="button"
              className="btn btn--primary btn--sm"
              onClick={() => void endorse()}
              disabled={mine || busy}
            >
              {mine ? 'You have agreed' : busy ? 'Recording…' : 'Agree to this'}
            </button>
          </div>
        )}
      </div>
    </li>
  );
}
