import { ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Failed, Result } from '../components/states';
import { Field, Seal } from '../components/ui';
import {
  ApiError, RECORD_LABEL, api, recordLabel, shortMsp,
  type AccessRequest, type Grant, type LedgerRecord, type Org,
} from '../lib/api';
import { longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import './lightbox.css';

/**
 * The Lightbox — the buyer's portal.
 *
 * A buyer's whole job here is to ask one narrow question. So the screen is one
 * column on a wide empty field: nothing to scan, nothing to choose between,
 * just the question being composed.
 *
 * The constraint is stated before the first input rather than after the last,
 * because it is the reassurance that makes the request acceptable to the
 * factory on the other end.
 *
 * Sending it writes a real request the factory sees on its own dashboard and
 * can answer. It used to set a boolean and show a confirmation for something
 * that had not happened.
 */
export default function Lightbox() {
  const { role } = useSession();
  const world = useApi(
    () => Promise.all([api.orgs(), api.grants(), api.requests(), api.records()]) as
      Promise<[Org[], Grant[], AccessRequest[], LedgerRecord[]]>,
    [],
  );

  return (
    <div className="lbx">
      <Result query={world} pendingLabel="Reading what you hold">
        {([orgs, grants, requests, records]) => (
          <>
            <Ask
              factories={orgs.filter((o) => o.kind === 'factory')}
              periods={[...new Set(records.map((r) => r.period))].sort().reverse()}
              onSent={world.reload}
              org={role?.org ?? ''}
            />

            <aside className="lbx__side">
              <p className="stamp-type lbx__side-head">Your requests</p>
              {requests.length === 0 ? (
                <p className="small lbx__side-note">
                  Nothing asked for yet. A request names a period; the grant that
                  answers it names a document.
                </p>
              ) : (
                <ul className="reqlist">
                  {requests.map((r) => (
                    <li key={r.id}>
                      <div className="reqrow">
                        <span className="reqrow__top">
                          <span className="reqrow__org">{shortMsp(r.supplier_msp)}</span>
                          <Seal
                            tone={
                              r.status === 'granted' ? 'sealed'
                                : r.status === 'pending' ? 'pending' : 'broken'
                            }
                          >
                            {r.status}
                          </Seal>
                        </span>
                        <span className="mono reqrow__field">{r.field_name}</span>
                        <span className="small reqrow__meta">
                          {recordLabel(r.record_type)} · {period(r.period)} · {r.purpose_code}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              <p className="stamp-type lbx__side-head">Grants you hold</p>
              {grants.length === 0 ? (
                <p className="small lbx__side-note">No grant is live against you.</p>
              ) : (
                <ul className="reqlist">
                  {grants.slice(0, 8).map((g) => (
                    <li key={g.grant_id}>
                      <Link
                        to={`/factory/records/${encodeURIComponent(g.record_id)}`}
                        className="reqrow"
                      >
                        <span className="reqrow__top">
                          <span className="reqrow__org">{shortMsp(g.owner_msp)}</span>
                          <Seal
                            tone={
                              g.status === 'active' ? 'sealed'
                                : g.status === 'revoked' ? 'broken' : 'inert'
                            }
                          >
                            {g.status}
                          </Seal>
                        </span>
                        <span className="mono reqrow__field">{g.field_name}</span>
                        <span className="small reqrow__meta">
                          {g.purpose_code} · until {longDate(g.expires_at)}
                        </span>
                        {g.revoked_reason && (
                          <span className="small reqrow__reason">{g.revoked_reason}</span>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              {grants.length > 8 && (
                <p className="small lbx__side-note">
                  Showing 8 of {grants.length}. The rest are on{' '}
                  <Link to="/factory/records">your records</Link>.
                </p>
              )}

              <p className="small lbx__side-note">
                A grant covers one field of one record for a fixed window. Asking for
                anything outside it is refused by the contract, not by the interface.
              </p>
            </aside>
          </>
        )}
      </Result>
    </div>
  );
}

function Ask({
  factories, periods, onSent, org,
}: {
  factories: Org[];
  periods: string[];
  onSent: () => void;
  org: string;
}) {
  const [supplier, setSupplier] = useState('');
  const [recordType, setRecordType] = useState('payroll_register');
  const [per, setPer] = useState(periods[0] ?? '');
  const [field, setField] = useState('');
  const [purpose, setPurpose] = useState('ETH-WAGE-VERIFY');
  const [expires, setExpires] = useState('2028-12-31');
  const [sent, setSent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const ready = supplier !== '' && field.trim().length > 0 && per !== '';

  const send = async () => {
    setBusy(true);
    setFailure(null);
    try {
      await api.ask({
        supplier_msp: supplier,
        record_type: recordType,
        period: per,
        purpose_code: purpose,
        field_name: field.trim(),
        expires_at: `${expires}T00:00:00Z`,
      });
      setSent(supplier);
      onSent();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'the request was not sent'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="lbx__form">
      <p className="stamp-type lbx__eyebrow">{org}</p>
      <h1>Ask for one fact.</h1>
      <p className="lead lbx__constraint">
        You will receive the single value you name and nothing else — not the row it
        sits in, not the file it came from. Narrow the question as far as you can.
      </p>

      {sent ? (
        <div className="lbx__sent">
          <Seal tone="pending">Sent</Seal>
          <h3 className="lbx__sent-head">Your request is with {shortMsp(sent)}.</h3>
          <p className="small lbx__sent-body">
            They decide whether to grant it, against which record, and for how long. It
            is on their dashboard now. If they grant it, you will be able to verify that
            one value and nothing more.
          </p>
          <button
            type="button"
            className="btn btn--secondary btn--md"
            onClick={() => setSent(null)}
          >
            Ask for another
          </button>
        </div>
      ) : (
        <form
          className="lbx__fields"
          onSubmit={(e) => { e.preventDefault(); void send(); }}
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
                <option key={f.msp_id} value={f.msp_id}>{f.name}</option>
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
            <Field label="Period" id="period" hint="Periods the ledger actually holds.">
              <select
                id="period"
                className="input"
                value={per}
                onChange={(e) => setPer(e.target.value)}
              >
                {periods.map((p) => (
                  <option key={p} value={p}>{period(p)}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field
            label="The exact field you need"
            id="field"
            hint="One field. e.g. net_pay_bdt, cas_number, certificate_id"
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
            <input
              id="purpose"
              className="input mono"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
            />
          </Field>

          <Field
            label="Access expires"
            id="expiry"
            hint="After this date the grant stops working by itself."
          >
            <input
              id="expiry"
              className="input"
              type="date"
              value={expires}
              onChange={(e) => setExpires(e.target.value)}
            />
          </Field>

          {failure && <Failed error={failure} />}

          <button type="submit" className="btn btn--primary btn--lg" disabled={!ready || busy}>
            {busy ? 'Sending…' : 'Send the request'} <ArrowRight size={16} />
          </button>
          {!ready && (
            <p className="small lbx__why">
              Choose a factory and name a field before sending.
            </p>
          )}
        </form>
      )}
    </div>
  );
}
