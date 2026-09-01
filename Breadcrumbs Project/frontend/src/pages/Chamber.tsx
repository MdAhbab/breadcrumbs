import { useState } from 'react';

import { ConsortiumMesh } from '../components/ConsortiumMesh';
import { MOTIONS, ORGS, type Motion } from '../lib/data';
import { longDate } from '../lib/format';
import './chamber.css';

/**
 * The Chamber — Rafiqul's console.
 *
 * These are decisions of record, not settings, so the grammar is a docket:
 * case numbers, motions set as readable prose rather than truncated card text,
 * and endorsement shown as seal impressions being affixed rather than as a
 * progress bar. When a motion carries, a stamp rotates in at an angle, the way
 * a rubber stamp lands on paper.
 */
export default function Chamber() {
  const [tab, setTab] = useState<'motions' | 'network' | 'register'>('motions');
  const [motions, setMotions] = useState<Motion[]>(MOTIONS);

  const endorse = (id: string) => {
    setMotions((prev) =>
      prev.map((m) => {
        if (m.id !== id || m.endorsers.includes('BGMEAConsortiumMSP')) return m;
        const endorsers = [...m.endorsers, 'BGMEAConsortiumMSP'];
        return {
          ...m,
          endorsers,
          status: endorsers.length >= m.required ? 'approved' : 'pending',
        };
      }),
    );
  };

  return (
    <div className="chamber">
      <header className="ch__head">
        <div>
          <p className="stamp-type ch__eyebrow">BGMEA Consortium · governance</p>
          <h1>The chamber</h1>
          <p className="lead ch__lede">
            {motions.filter((m) => m.status === 'pending').length} motions open ·{' '}
            {ORGS.length} members of record
          </p>
        </div>
        <div className="ch__tabs" role="tablist">
          <button
            role="tab"
            aria-selected={tab === 'motions'}
            className={`ch__tab ${tab === 'motions' ? 'is-on' : ''}`}
            onClick={() => setTab('motions')}
          >
            Motions
          </button>
          <button
            role="tab"
            aria-selected={tab === 'network'}
            className={`ch__tab ${tab === 'network' ? 'is-on' : ''}`}
            onClick={() => setTab('network')}
          >
            Network
          </button>
          <button
            role="tab"
            aria-selected={tab === 'register'}
            className={`ch__tab ${tab === 'register' ? 'is-on' : ''}`}
            onClick={() => setTab('register')}
          >
            Register
          </button>
        </div>
      </header>

      {tab === 'network' && <ConsortiumMesh />}

      {tab === 'motions' && (
        <ol className="docket">
          {motions.map((m) => {
            const carried = m.endorsers.length >= m.required;
            const mine = m.endorsers.includes('BGMEAConsortiumMSP');
            return (
              <li key={m.id} className={`motion ${carried ? 'is-carried' : ''}`}>
                <div className="motion__margin">
                  <p className="mono motion__case">{m.caseNo}</p>
                  <p className="stamp-type motion__kind">{m.kind.replace('_', ' ')}</p>
                  <p className="small motion__dates">
                    opened {longDate(m.openedAt)}
                    <br />
                    {carried ? 'resolved' : `${m.daysLeft} days remaining`}
                  </p>
                </div>

                <div className="motion__body">
                  <h2 className="motion__title">{m.title}</h2>
                  <p className="motion__prose">{m.body}</p>

                  {/* The seal ledger: impressions, not a progress bar. */}
                  <div className="seals">
                    <p className="stamp-type seals__label">
                      {m.endorsers.length} of {m.required} sealed
                    </p>
                    <div className="seals__row">
                      {Array.from({ length: m.required }, (_, i) => {
                        const org = m.endorsers[i];
                        return (
                          <span
                            key={i}
                            className={`impression ${org ? 'is-filled' : ''}`}
                            title={org ?? 'awaiting endorsement'}
                          >
                            {org ? org.replace('MSP', '').slice(0, 2).toUpperCase() : ''}
                          </span>
                        );
                      })}
                    </div>
                    <p className="small seals__who">
                      {m.endorsers.length
                        ? m.endorsers.map((e) => e.replace('MSP', '')).join(' · ')
                        : 'No endorsements yet.'}
                    </p>
                  </div>

                  {carried ? (
                    <div className="carried">
                      <span className="carried__stamp stamp-type">Resolved</span>
                      <p className="small carried__note">
                        Threshold reached. The outcome and the endorser set are on the
                        ledger and cannot be quietly revised.
                      </p>
                    </div>
                  ) : (
                    <div className="motion__actions">
                      <button
                        type="button"
                        className="btn btn--primary btn--sm"
                        onClick={() => endorse(m.id)}
                        disabled={mine}
                      >
                        {mine ? 'You have sealed this' : 'Affix your seal'}
                      </button>
                      <button type="button" className="btn btn--ghost btn--sm">
                        Request more information
                      </button>
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {tab === 'register' && (
        <div className="register">
          <p className="stamp-type register__cap">Members of record</p>
          <table className="regtable">
            <thead>
              <tr>
                <th scope="col">Organisation</th>
                <th scope="col">MSP identity</th>
                <th scope="col">Role</th>
                <th scope="col">Country</th>
                <th scope="col">Admitted</th>
              </tr>
            </thead>
            <tbody>
              {ORGS.map((o) => (
                <tr key={o.mspId}>
                  <th scope="row">{o.name}</th>
                  <td className="mono">{o.mspId}</td>
                  <td className="regtable__role">{o.kind}</td>
                  <td>{o.country}</td>
                  <td className="mono dim">{longDate(o.joined)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small register__note">
            Admission and suspension are motions of this chamber. A member cannot be added
            or removed by whoever runs the infrastructure.
          </p>
        </div>
      )}
    </div>
  );
}
