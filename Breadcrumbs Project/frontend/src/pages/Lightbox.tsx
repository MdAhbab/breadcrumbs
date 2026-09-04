import { ArrowRight, Plus } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { Failed, Result } from '../components/states';
import { Tech } from '../components/Tech';
import { Field, Seal } from '../components/ui';
import {
  ApiError, PURPOSE_LABEL, RECORD_LABEL, api, orderGrants, purposeLabel, recordLabel, shortMsp,
  type AccessRequest, type Grant, type LedgerRecord, type Org,
} from '../lib/api';
import { longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import { useFieldLabel } from '../lib/useFieldLabel';
import './lightbox.css';

/**
 * The buyer's screen.
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
  const labelOf = useFieldLabel();
  const [shown, setShown] = useState(8);
  // Set when a row asks the form to point itself at the same document again.
  const [askMore, setAskMore] = useState<
    { supplierMsp: string; recordType: string; period: string } | null
  >(null);
  const world = useApi(
    () => Promise.all([api.orgs(), api.grants(), api.requests(), api.records()]) as
      Promise<[Org[], Grant[], AccessRequest[], LedgerRecord[]]>,
    [],
  );

  return (
    <div className="lbx">
      <Result query={world} pendingLabel="Reading what you hold">
        {([orgs, grants, requests, records]) => {
          // Grants carry a record_id and nothing else about the document. The
          // rows need its type and period to be readable, and the page has
          // already fetched every record, so resolve them here rather than
          // asking the API a second time.
          const byId = new Map(records.map((r) => [r.record_id, r]));
          // Ordered before it is truncated.
          //
          // `list_grants` returns the chaincode's key order, so this buyer's 259
          // seeded grants arrive as g-0003 … g-0313 and a grant answering a
          // request it made this morning — g-br-002 — sorts last. Showing the
          // first eight of that meant the one grant the buyer was waiting for
          // was the one it could not see, and the demo dead-ended at the step
          // that matters most. `orderGrants` says why a date sort does not fix
          // it either.
          const newest = orderGrants(grants, requests);
          // One list, not two.
          //
          // A request and the access it produced are the same story at two
          // moments, and the sidebar used to print both: "Apex Textile ·
          // granted" directly above "Apex Textile · active" for one thing the
          // buyer asked for once. Nobody reading that can tell whether they
          // have one piece of access or two.
          const items = mergeAsked(requests, newest, byId, labelOf);
          return (
          <>
            <Ask
              factories={orgs.filter((o) => o.kind === 'factory' && o.on_document_channel)}
              periods={[...new Set(records.map((r) => r.period))].sort().reverse()}
              onSent={world.reload}
              org={role?.org ?? ''}
              prefill={askMore}
              onPrefilled={() => setAskMore(null)}
            />

            <aside className="lbx__side">
              <p className="stamp-type lbx__side-head">What you asked for</p>
              {items.length === 0 ? (
                <p className="small lbx__side-note">
                  You have not asked for anything yet. Use the form to ask a factory
                  for one figure.
                </p>
              ) : (
                <ul className="reqlist">
                  {items.slice(0, shown).map((it) => (
                    <AskedRow key={it.key} item={it} onAskMore={setAskMore} />
                  ))}
                </ul>
              )}

              {items.length > shown && (
                <button
                  type="button"
                  className="btn btn--ghost btn--sm lbx__morebtn"
                  onClick={() => setShown((n) => n + 8)}
                >
                  Show {Math.min(8, items.length - shown)} more
                </button>
              )}

              <p className="small lbx__side-note">
                Each one covers a single column of a single record, until the date on
                it. Anything wider is refused by the contract itself, not by this
                screen. Opening a file you hold is a read: it writes nothing to the
                ledger and leaves no trace on it. Only checking a figure does.
              </p>
            </aside>
          </>
          );
        }}
      </Result>
    </div>
  );
}

/* ------------------------------------------------------------ one list ---- */

/** Where a thing you asked for has got to, in words rather than in states. */
type Stage = 'waiting' | 'open' | 'refused' | 'ended';

interface Asked {
  key: string;
  org: string;
  field: string;
  what: string;
  purpose: string;
  stage: Stage;
  reason?: string;
  grantId?: string;
  recordId?: string;
  until?: string;
  /** Enough to ask the same factory for more of the same document. */
  again?: { supplierMsp: string; recordType: string; period: string };
}

const STAGE_WORD: Record<Stage, string> = {
  waiting: 'Waiting for the factory',
  open: 'You can see this',
  refused: 'Refused',
  ended: 'Access ended',
};

const STAGE_TONE: Record<Stage, 'sealed' | 'pending' | 'broken' | 'inert'> = {
  waiting: 'pending',
  open: 'sealed',
  refused: 'inert',
  ended: 'broken',
};

/**
 * Requests and the access they produced, folded into one list.
 *
 * They were two lists, and a request the factory had just answered appeared in
 * both: once as "granted" and once, immediately below, as "active". They are
 * not two things. A buyer reading that cannot tell whether it holds one piece
 * of access or two, which is the single fact this screen exists to report.
 *
 * Requests come first because they carry the whole story, including the ones
 * that were refused and so never became access at all. Any access that no
 * request accounts for is appended, since a factory may hand something over
 * without being asked.
 */
function mergeAsked(
  requests: AccessRequest[],
  grants: Grant[],
  byId: Map<string, LedgerRecord>,
  labelOf: (recordType: string, field: string) => string,
): Asked[] {
  const describe = (recordType: string, per: string) =>
    `${recordLabel(recordType)}, ${period(per)}`;

  // A request knows it was answered but not when that answer runs out; the
  // grant it produced does. Joining them here is what lets every open row carry
  // the same end date, rather than only the ones that came in as grants.
  const byGrantId = new Map(grants.map((g) => [g.grant_id, g]));

  const fromRequests: Asked[] = requests.map((r) => {
    const stage: Stage =
      r.status === 'pending' ? 'waiting'
        : r.status === 'declined' ? 'refused'
          : r.grant_status === 'revoked' ? 'ended' : 'open';
    const grant = r.grant_id ? byGrantId.get(r.grant_id) : undefined;
    return {
      key: `r-${r.id}`,
      org: shortMsp(r.supplier_msp),
      field: labelOf(r.record_type, r.field_name),
      what: describe(r.record_type, r.period),
      purpose: purposeLabel(r.purpose_code),
      stage,
      reason: r.decline_reason ?? r.grant_revoked_reason ?? undefined,
      grantId: r.grant_status === 'active' ? r.grant_id ?? undefined : undefined,
      recordId: r.grant_record_id ?? undefined,
      until: stage === 'open' ? grant?.expires_at : undefined,
      again: {
        supplierMsp: r.supplier_msp,
        recordType: r.record_type,
        period: r.period,
      },
    };
  });

  const accountedFor = new Set(
    requests.map((r) => r.grant_id).filter((id): id is string => Boolean(id)),
  );

  const fromGrants: Asked[] = grants
    .filter((g) => !accountedFor.has(g.grant_id))
    .map((g) => {
      const record = byId.get(g.record_id);
      return {
        key: `g-${g.grant_id}`,
        org: shortMsp(g.owner_msp),
        field: labelOf(record?.record_type ?? '', g.field_name),
        what: record ? describe(record.record_type, record.period) : g.record_id,
        purpose: purposeLabel(g.purpose_code),
        stage: g.status === 'active' ? 'open' : g.status === 'revoked' ? 'ended' : 'refused',
        reason: g.revoked_reason ?? undefined,
        grantId: g.status === 'active' ? g.grant_id : undefined,
        recordId: g.record_id,
        until: g.status === 'active' ? g.expires_at : undefined,
        again: record
          ? {
            supplierMsp: g.owner_msp,
            recordType: record.record_type,
            period: record.period,
          }
          : undefined,
      };
    });

  // Anything needing a decision or offering one sits at the top; the rest keeps
  // the order it arrived in.
  const rank: Record<Stage, number> = { waiting: 0, open: 1, refused: 2, ended: 3 };
  return [...fromRequests, ...fromGrants].sort((a, b) => rank[a.stage] - rank[b.stage]);
}

function AskedRow({
  item, onAskMore,
}: {
  item: Asked;
  onAskMore: (from: NonNullable<Asked['again']>) => void;
}) {
  return (
    <li>
      <div className={`reqrow reqrow--${item.stage}`}>
        <span className="reqrow__top">
          <span className="reqrow__org">{item.org}</span>
          <Seal tone={STAGE_TONE[item.stage]}>{STAGE_WORD[item.stage]}</Seal>
        </span>

        <span className="reqrow__field">{item.field}</span>
        <span className="small reqrow__meta">
          {item.what} · {item.purpose}
          {item.until && ` · until ${longDate(item.until)}`}
        </span>

        {item.reason && <span className="small reqrow__reason">{item.reason}</span>}

        <span className="reqrow__acts">
          {/* Straight into the file this permission was written against.
              The link carries the grant rather than the document, because a
              buyer holds permissions and not documents — the verify screen
              resolves one to the other. It used to carry the grant to a screen
              that read only `?record=`, so every one of these opened whichever
              document happened to sort first.

              Opening it is a read. Nothing is proposed to the chain and no
              receipt is written until a figure is actually checked, which is
              why this says "open" and not "prove". */}
          {item.grantId && (
            <Link
              to={`/verify?grant=${encodeURIComponent(item.grantId)}`}
              className="reqrow__prove"
            >
              Open the file <ArrowRight size={12} />
            </Link>
          )}
          {item.grantId && (
            <span className="small reqrow__hint">
              Read the figure released to you, and check it against the ledger.
            </span>
          )}
          {/* Holding one column of a register is the moment you find out you
              need the next one, and until now that meant filling the form in
              again from the top. */}
          {item.again && item.stage !== 'waiting' && (
            <button
              type="button"
              className="reqrow__more"
              onClick={() => onAskMore(item.again!)}
            >
              <Plus size={11} /> Ask for more from this
            </button>
          )}
        </span>

        <Tech>
          {item.recordId && <span className="mono reqrow__doc">{item.recordId}</span>}
        </Tech>
      </div>
    </li>
  );
}

function Ask({
  factories, periods, onSent, org, prefill, onPrefilled,
}: {
  factories: Org[];
  periods: string[];
  onSent: () => void;
  org: string;
  prefill: { supplierMsp: string; recordType: string; period: string } | null;
  onPrefilled: () => void;
}) {
  const [supplier, setSupplier] = useState('');
  const [recordType, setRecordType] = useState('payroll_register');
  const [per, setPer] = useState(periods[0] ?? '');
  const [picked, setPicked] = useState<string[]>([]);
  const [purpose, setPurpose] = useState('ETH-WAGE-VERIFY');
  const [expires, setExpires] = useState('2028-12-31');
  const [sent, setSent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);
  // The columns that actually exist, read off the documents rather than
  // remembered by whoever is filling the form in.
  const fields = useApi(() => api.recordFields(), []);

  // Columns chosen for payroll mean nothing once the kind of record changes.
  useEffect(() => { setPicked([]); }, [recordType]);

  // "Ask for more from this" points the form at the same factory, kind and
  // month, and leaves the columns empty — the whole reason for pressing it is
  // that the ones already held are not the ones now needed.
  useEffect(() => {
    if (!prefill) return;
    setSupplier(prefill.supplierMsp);
    setRecordType(prefill.recordType);
    setPer(prefill.period);
    setPicked([]);
    setSent(null);
    onPrefilled();
  }, [prefill, onPrefilled]);

  const available = (fields.data?.[recordType] ?? []).filter((f) => f.requestable);
  const blocked = (fields.data?.[recordType] ?? []).filter((f) => !f.requestable);
  const ready = supplier !== '' && picked.length > 0 && per !== '';

  const toggle = (name: string) =>
    setPicked((current) =>
      current.includes(name) ? current.filter((c) => c !== name) : [...current, name]);

  const send = async () => {
    setBusy(true);
    setFailure(null);
    try {
      await api.ask({
        supplier_msp: supplier,
        record_type: recordType,
        period: per,
        purpose_code: purpose,
        field_names: picked,
        expires_at: `${expires}T00:00:00Z`,
      });
      setSent(supplier);
      setPicked([]);
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
      <h1>Request one piece of data.</h1>
      <p className="lead lbx__constraint">
        You will get the one figure you ask for and nothing else. Not the rest of the
        row, and not the rest of the file. The factory decides whether to release it.
      </p>

      {sent ? (
        <div className="lbx__sent">
          <Seal tone="pending">Sent</Seal>
          <h3 className="lbx__sent-head">Your request is with {shortMsp(sent)}.</h3>
          <p className="small lbx__sent-body">
            They decide whether to release it, from which record, and for how long. It
            is on their screen now. If they say yes, you will be able to check that one
            figure and nothing more.
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
          <Field label="Which factory" id="supplier">
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
            <Field label="Which kind of record" id="rtype">
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
            <Field label="Which month" id="period" hint="Only months the ledger actually has.">
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

          {/* Tick boxes rather than one dropdown. Each one still becomes its
              own separate permission that the factory answers on its own; what
              changed is that asking for four of them is one action instead of
              four identical trips through this form. */}
          <fieldset className="picker">
            <legend className="field__label">Which figures</legend>
            <p className="field__hint small">
              Tick everything you need. Each one is released separately, and the factory
              can say yes to some and no to others.
            </p>
            <div className="picker__grid">
              {available.map((f) => (
                <label key={f.name} className="picker__item">
                  <input
                    type="checkbox"
                    checked={picked.includes(f.name)}
                    onChange={() => toggle(f.name)}
                  />
                  <span>{f.label}</span>
                </label>
              ))}
            </div>
            {picked.length > 0 && (
              <p className="small picker__count">
                {picked.length} selected. That is {picked.length} separate
                {picked.length === 1 ? ' permission' : ' permissions'} for the factory
                to decide on.
              </p>
            )}
          </fieldset>

          {blocked.length > 0 && (
            <p className="small lbx__blocked">
              {blocked.map((f) => f.label).join(', ')} cannot be asked for at all. Those
              identify a person, and no permission opens them.
            </p>
          )}

          <Field
            label="What you need it for"
            id="purpose"
            hint="This goes on the ledger next to the permission, so the factory can see why it was asked for."
          >
            <select
              id="purpose"
              className="input"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
            >
              {Object.entries(PURPOSE_LABEL).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </Field>

          <Field
            label="Access ends on"
            id="expiry"
            hint="After this date it stops working on its own. Nobody has to remember to end it."
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
            {busy
              ? 'Sending…'
              : `Send the request${picked.length > 1 ? ` (${picked.length} figures)` : ''}`}{' '}
            <ArrowRight size={16} />
          </button>
          {!ready && (
            <p className="small lbx__why">
              Choose a factory and tick at least one figure before sending.
            </p>
          )}
        </form>
      )}
    </div>
  );
}
