import { ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Field, Seal } from '../components/ui';
import { GRANTS, ORGS, PURPOSE_CODES, RECORD_LABEL, orgName } from '../lib/data';
import { longDate, period } from '../lib/format';
import './lightbox.css';

/**
 * The Lightbox — James's portal.
 *
 * A buyer's whole job here is to ask one narrow question. So the screen is one
 * column on a wide empty field: nothing to scan, nothing to choose between,
 * just the question being composed.
 *
 * The constraint is stated before the first input rather than after the last,
 * because it is the reassurance that makes the request acceptable to the
 * factory on the other end.
 */
export default function Lightbox() {
  const [supplier, setSupplier] = useState('');
  const [recordType, setRecordType] = useState('payroll_register');
  const [field, setField] = useState('');
  const [purpose, setPurpose] = useState('ETH-WAGE-VERIFY');
  const [sent, setSent] = useState(false);

  const factories = ORGS.filter((o) => o.kind === 'factory');
  const mine = GRANTS.filter((g) => g.requesterMsp === 'PrimarkSourcingMSP');
  const ready = supplier && field.trim().length > 0;

  return (
    <div className="lbx">
      <div className="lbx__form">
        <p className="stamp-type lbx__eyebrow">Primark Sourcing Ltd</p>
        <h1>Ask for one fact.</h1>
        <p className="lead lbx__constraint">
          You will receive the single value you name and nothing else — not the row it
          sits in, not the file it came from. Narrow the question as far as you can.
        </p>

        {sent ? (
          <div className="lbx__sent">
            <Seal tone="pending">Sent</Seal>
            <h3 className="lbx__sent-head">Your request is with {orgName(supplier)}.</h3>
            <p className="small lbx__sent-body">
              They decide whether to grant it, for how long, and for which field. If they
              do, you will be able to verify that value and nothing more.
            </p>
            <button type="button" className="btn btn--secondary btn--md" onClick={() => setSent(false)}>
              Ask for another
            </button>
          </div>
        ) : (
          <form
            className="lbx__fields"
            onSubmit={(e) => {
              e.preventDefault();
              setSent(true);
            }}
          >
            <Field label="Supplier factory" id="supplier">
              <select
                id="supplier"
                className="input"
                value={supplier}
                onChange={(e) => setSupplier(e.target.value)}
              >
                <option value="">Choose a factory…</option>
                {factories.map((f) => (
                  <option key={f.mspId} value={f.mspId}>{f.name}</option>
                ))}
              </select>
            </Field>

            <div className="lbx__pair">
              <Field label="Record type" id="rtype">
                <select
                  id="rtype"
                  className="input"
                  value={recordType}
                  onChange={(e) => setRecordType(e.target.value)}
                >
                  {Object.entries(RECORD_LABEL).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </Field>
              <Field label="Period" id="period">
                <input id="period" className="input" type="month" defaultValue="2026-07" />
              </Field>
            </div>

            <Field
              label="The exact field you need"
              id="field"
              hint="One field. e.g. net_pay_bdt, svhc_ppm, certificate_id"
            >
              <input
                id="field"
                className="input mono"
                placeholder="net_pay_bdt"
                value={field}
                onChange={(e) => setField(e.target.value)}
              />
            </Field>

            <Field label="Purpose" id="purpose" hint="Recorded on the ledger alongside the grant.">
              <select
                id="purpose"
                className="input"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
              >
                {Object.entries(PURPOSE_CODES).map(([k, v]) => (
                  <option key={k} value={k}>{v} — {k}</option>
                ))}
              </select>
            </Field>

            <Field label="Access expires" id="expiry" hint="After this date the grant stops working by itself.">
              <input id="expiry" className="input" type="date" defaultValue="2026-09-30" />
            </Field>

            <button type="submit" className="btn btn--primary btn--lg" disabled={!ready}>
              Send the request <ArrowRight size={16} />
            </button>
            {!ready && (
              <p className="small lbx__why">
                Choose a factory and name a field before sending.
              </p>
            )}
          </form>
        )}
      </div>

      <aside className="lbx__side">
        <p className="stamp-type lbx__side-head">Your requests</p>
        <ul className="reqlist">
          {mine.map((g) => (
            <li key={g.grantId}>
              <Link to="/verify/vr-001" className="reqrow">
                <span className="reqrow__top">
                  <span className="reqrow__org">{orgName(g.ownerMsp)}</span>
                  <Seal
                    tone={
                      g.status === 'active' ? 'sealed'
                        : g.status === 'pending' ? 'pending'
                          : g.status === 'revoked' ? 'broken' : 'inert'
                    }
                  >
                    {g.status}
                  </Seal>
                </span>
                <span className="mono reqrow__field">{g.fieldName}</span>
                <span className="small reqrow__meta">
                  {PURPOSE_CODES[g.purposeCode]} · until {longDate(g.expiresAt)}
                </span>
                {g.revokedReason && (
                  <span className="small reqrow__reason">{g.revokedReason}</span>
                )}
              </Link>
            </li>
          ))}
        </ul>
        <p className="small lbx__side-note">
          A grant covers one field of one record for a fixed window. Asking for anything
          outside it is refused by the contract, not by the interface.
        </p>
        <p className="small lbx__side-note">
          Sample period shown: {period('2026-07')}.
        </p>
      </aside>
    </div>
  );
}
