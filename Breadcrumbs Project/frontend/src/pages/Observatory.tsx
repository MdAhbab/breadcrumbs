import { Eye } from 'lucide-react';

import { Frosted, Seal } from '../components/ui';
import { BOLTS, MOTIONS, ORGS, RECORD_LABEL, SLA_SERIES, orgName } from '../lib/data';
import { commas, longDate } from '../lib/format';
import './observatory.css';

/**
 * The Observatory — Aziz's view.
 *
 * The most interesting design problem in the product, because a regulator's
 * defining characteristic is what they may *not* see.
 *
 * Most software treats permissions as absence: it hides what you cannot access,
 * and you learn nothing. Here the restricted regions stay on the page behind
 * glass — the layout, the row count and the shape of the data are all visible,
 * the content is not, and the exact lawful basis required is stated on each one.
 * Absence teaches nothing; a drawn boundary teaches the rule.
 *
 * This is honest rather than decorative: the API refuses this role's token for
 * the same endpoints, so the glass is showing a real limit.
 */
export default function Observatory() {
  const uptime = SLA_SERIES.reduce((a, p) => a + p.uptime, 0) / SLA_SERIES.length;
  const verifications = SLA_SERIES.reduce((a, p) => a + p.verifications, 0);

  return (
    <div className="obs">
      {/* A permanent condition of the view, not a dismissible banner. */}
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

      <header className="obs__head">
        <p className="stamp-type obs__eyebrow">Dept. of Labour, Bangladesh</p>
        <h1>Observatory</h1>
      </header>

      {/* -- what is visible ---------------------------------------------- */}
      <section className="obs__section">
        <p className="stamp-type obs__label">Visible to you</p>
        <div className="figures">
          <Figure n={ORGS.filter((o) => o.kind === 'factory').length} label="active factories" />
          <Figure n={ORGS.length} label="organisations in the consortium" />
          <Figure n={MOTIONS.filter((m) => m.status === 'pending').length} label="motions open" />
          <Figure n={`${uptime.toFixed(3)}%`} label="portal uptime, August" />
          <Figure n={commas(verifications)} label="verifications this month" />
          <Figure n={4} label="schema versions in use" />
        </div>
      </section>

      <section className="obs__section">
        <p className="stamp-type obs__label">Governance events</p>
        <ol className="events">
          {MOTIONS.map((m) => (
            <li key={m.id} className="event">
              <span className="mono event__case">{m.caseNo}</span>
              <span className="event__body">
                <span className="event__title">{m.title}</span>
                <span className="small event__meta">
                  {m.kind.replace('_', ' ')} · opened {longDate(m.openedAt)} · BGMEA Consortium
                </span>
              </span>
              <Seal tone={m.status === 'approved' ? 'sealed' : 'pending'}>{m.status}</Seal>
            </li>
          ))}
        </ol>
      </section>

      {/* -- what is not, and why ----------------------------------------- */}
      <section className="obs__section">
        <p className="stamp-type obs__label obs__label--closed">Present, but closed to you</p>
        <p className="small obs__explain">
          These views exist and hold data. Your role does not carry the capability to read
          them, and the server refuses the request — not merely the interface.
        </p>

        <div className="obs__closed">
          <Frosted reason="Factory records require a separate lawful-basis access grant.">
            <div className="ghost">
              <p className="stamp-type ghost__head">Committed records · Apex Textile Ltd</p>
              <table className="ghosttable">
                <tbody>
                  {BOLTS.map((b) => (
                    <tr key={b.recordId}>
                      <td>{RECORD_LABEL[b.recordType]}</td>
                      <td>{b.period}</td>
                      <td>{commas(b.rowCount)} threads</td>
                      <td>{b.merkleRoot.slice(0, 18)}…</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Frosted>

          <Frosted reason="Grant-level detail names individual counterparties and is out of scope.">
            <div className="ghost">
              <p className="stamp-type ghost__head">Access grants · all factories</p>
              <table className="ghosttable">
                <tbody>
                  {ORGS.slice(0, 5).map((o) => (
                    <tr key={o.mspId}>
                      <td>{orgName(o.mspId)}</td>
                      <td>net_pay_bdt</td>
                      <td>ETH-WAGE-VERIFY</td>
                      <td>expires 30 Sep 2026</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Frosted>
        </div>

        <div className="obs__request">
          <p className="small">
            A lawful-basis grant is itself a motion of the consortium chamber, recorded on
            the ledger like any other. Requesting one leaves a trail; so does approving it.
          </p>
          <button type="button" className="btn btn--secondary btn--sm">
            Request a lawful-basis grant
          </button>
        </div>
      </section>
    </div>
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
