import { KeyRound, Undo2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Empty, Failed, Result } from '../components/states';
import { PageHead, Seal } from '../components/ui';
import {
  ApiError, api, purposeLabel, recordLabel, shortMsp,
  type AccessRequest, type Grant, type LedgerRecord, type VerificationRow,
} from '../lib/api';
import { commas, dateTime, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import './access.css';
import { useFieldLabel } from '../lib/useFieldLabel';

const PAGE = 30;

/**
 * Who may read a thread — the factory's side of every access decision.
 *
 * The factory is one half of every disclosure this product makes and had no
 * screen for it. Granting and declining lived in an unlabelled panel at the
 * bottom of the shift log; revoking existed only on a record's own page, one
 * grant at a time, and only if you already knew which of six hundred documents
 * it was on. The dashboard counted "grants you have revoked" on a page that
 * could not revoke one.
 *
 * The three sections are the three questions the job actually has: what is
 * waiting for me, what did I decide, and what is live right now. They are not
 * three views of one list — a request is a question that was asked, and a grant
 * is a fact on the ledger, and the difference between them is the whole
 * consent model.
 *
 * Nothing here can undo anything. A revocation is permanent and stays on the
 * chain with its reason; the way back from one is to grant the access again,
 * which writes a new grant with a new identifier and leaves both visible. That
 * is not a limitation being worked around, it is the property being preserved.
 */
export default function Access() {
  const { role } = useSession();
  const world = useApi(
    () => Promise.all([api.requests(), api.grants(), api.records(), api.verifications()]) as
      Promise<[AccessRequest[], Grant[], LedgerRecord[], VerificationRow[]]>,
    [],
  );

  return (
    <div className="acc">
      <Result query={world} pendingLabel="Reading your grants off the chain">
        {([requests, grants, records, verifications]) => {
          const pending = requests.filter((r) => r.status === 'pending');
          const answered = requests.filter((r) => r.status !== 'pending');
          const active = grants.filter((g) => g.status === 'active');

          return (
            <>
              <PageHead
                eyebrow={`${role?.org} · access`}
                title="Who can see what"
                lede={
                  'Each permission covers one column of one record, until a date you set. '
                  + 'The contract itself refuses anything wider. Withdrawing one is permanent, '
                  + 'and the reason goes on the ledger under your name. You can give access '
                  + 'again later, but only as a new permission, in the open.'
                }
                aside={
                  <div className="acc__counts">
                    <Tally n={pending.length} label="waiting on you" tone={pending.length ? 'warn' : 'calm'} />
                    <Tally n={active.length} label="live now" tone="calm" />
                    <Tally
                      n={grants.length - active.length}
                      label="expired or withdrawn"
                      tone="calm"
                    />
                    <Tally n={verifications.length} label="checks run" tone="calm" />
                  </div>
                }
              />

              <Awaiting requests={pending} records={records} onDone={world.reload} />
              <Answered requests={answered} records={records} onDone={world.reload} />
              <Issued grants={grants} records={records} onDone={world.reload} />
              <Verifications rows={verifications} />
            </>
          );
        }}
      </Result>
    </div>
  );
}

/* -- the shared write path ------------------------------------------------ */
/*
 * One busy key and one failure for the whole page. Every action here is a
 * ledger write or a decision about one, so two of them must never be in flight
 * at once — and a refusal is a result worth reading, so it is shown with the
 * contract's own sentence rather than swallowed.
 */
function useAction(onDone: () => void) {
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const act = async (key: string, run: () => Promise<unknown>) => {
    setBusy(key);
    setFailure(null);
    try {
      await run();
      onDone();
      return true;
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'that did not work'));
      return false;
    } finally {
      setBusy(null);
    }
  };

  return { busy, failure, act };
}

/* -- 1. what is waiting --------------------------------------------------- */

/**
 * Requests grouped the way they were sent.
 *
 * A buyer can now ask for four columns of one register in a single action, so
 * four separate rows here would be this screen losing information the buyer
 * took care to express. Requests sent together share a batch; anything older
 * groups by who asked, for what kind of record and for which month, which is
 * the same question arrived at a different way.
 */
function groupRequests(requests: AccessRequest[]): AccessRequest[][] {
  const groups = new Map<string, AccessRequest[]>();
  requests.forEach((r) => {
    const key = r.batch_id
      ?? `${r.requester_msp}|${r.record_type}|${r.period}|${r.purpose_code}`;
    groups.set(key, [...(groups.get(key) ?? []), r]);
  });
  return [...groups.values()];
}

function Awaiting({
  requests, records, onDone,
}: {
  requests: AccessRequest[];
  records: LedgerRecord[];
  onDone: () => void;
}) {
  const labelOf = useFieldLabel();
  const { busy, failure, act } = useAction(onDone);
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [declining, setDeclining] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [partial, setPartial] = useState<Record<string, string>>({});

  const groups = groupRequests(requests);

  return (
    <section className="acc__section">
      <h2 className="acc__h2">Waiting on you</h2>
      <p className="lead acc__lede">
        A request names a month. What you release names one document, so choosing
        which one is part of answering rather than a detail afterwards. Each column
        is released on its own, even when several were asked for together.
      </p>
      {failure && <Failed error={failure} />}

      {groups.length === 0 ? (
        <Empty title="Nothing waiting" detail="Every request you have been sent has an answer." />
      ) : (
        <ul className="acc__list">
          {groups.map((group) => {
            const first = group[0];
            const groupKey = first.batch_id ?? first.id;
            const candidates = records.filter(
              (x) => x.record_type === first.record_type && x.period === first.period,
            );
            const pick = chosen[groupKey] ?? candidates[0]?.record_id ?? '';
            const ids = group.map((r) => r.id);
            const working = busy === groupKey;
            const refusing = declining && ids.includes(declining) ? declining : null;

            return (
              <li key={groupKey} className="areq">
                <div className="areq__head">
                  <div>
                    <p className="areq__who">{shortMsp(first.requester_msp)}</p>
                    <p className="small areq__what">
                      wants{' '}
                      {group.length === 1 ? (
                        <strong>{labelOf(first.record_type, first.field_name)}</strong>
                      ) : (
                        <strong>{group.length} figures</strong>
                      )}{' '}
                      from {recordLabel(first.record_type)}, {period(first.period)} ·{' '}
                      <span>{purposeLabel(first.purpose_code)}</span>
                    </p>
                    <p className="small areq__when">
                      asked {longDate(first.requested_at)} · access would run to{' '}
                      {longDate(first.expires_at)}
                    </p>
                  </div>
                  <Seal tone="pending">
                    {group.length === 1 ? 'pending' : `${group.length} pending`}
                  </Seal>
                </div>

                {group.length > 1 && (
                  <ul className="areq__cols">
                    {group.map((r) => (
                      <li key={r.id} className="areq__col">
                        <span>{labelOf(r.record_type, r.field_name)}</span>
                        <button
                          type="button"
                          className="areq__colrefuse"
                          disabled={busy !== null}
                          onClick={() => { setDeclining(r.id); setReason(''); }}
                        >
                          refuse this one
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                {candidates.length === 0 ? (
                  <p className="small areq__none">
                    You have not published a {recordLabel(first.record_type).toLowerCase()}{' '}
                    for {period(first.period)}, so there is nothing to release. Refuse it,
                    or publish the record first.
                  </p>
                ) : (
                  <label className="areq__pick">
                    <span className="stamp-type">From which record</span>
                    <select
                      className="input"
                      value={pick}
                      onChange={(e) => setChosen({ ...chosen, [groupKey]: e.target.value })}
                    >
                      {candidates.map((c) => (
                        <option key={c.record_id} value={c.record_id}>
                          {c.site} · {commas(c.row_count)} rows · published{' '}
                          {longDate(c.committed_at)}
                        </option>
                      ))}
                    </select>
                    <span className="small areq__pickmeta">
                      {commas(candidates.length)} record
                      {candidates.length === 1 ? '' : 's'} match this month.
                      {pick && group.length === 1 && (
                        <> They receive {labelOf(first.record_type, first.field_name)} from
                          {' '}this one, and nothing else.</>
                      )}
                      {pick && group.length > 1 && (
                        <> They receive those {group.length} figures from this one, each as
                          {' '}its own permission you can withdraw separately.</>
                      )}
                    </span>
                  </label>
                )}

                {partial[groupKey] && (
                  <p className="small areq__partial">{partial[groupKey]}</p>
                )}

                {refusing ? (
                  <div className="areq__reason">
                    <p className="small areq__note">
                      Refusing{' '}
                      <strong>
                        {labelOf(
                          first.record_type,
                          group.find((r) => r.id === refusing)!.field_name,
                        )}
                      </strong>.
                    </p>
                    <input
                      className="input"
                      placeholder="Why are you refusing? The buyer is told."
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                    <div className="areq__actions">
                      <button
                        type="button"
                        className="btn btn--danger btn--sm"
                        disabled={busy === refusing}
                        onClick={() => {
                          void act(refusing, () => api.declineRequest(refusing, reason.trim()))
                            .then((ok) => {
                              if (!ok) return;
                              setDeclining(null);
                              setReason('');
                            });
                        }}
                      >
                        {busy === refusing ? 'Refusing…' : 'Refuse this one'}
                      </button>
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={() => { setDeclining(null); setReason(''); }}
                      >
                        Cancel
                      </button>
                    </div>
                    <p className="small areq__note">
                      Refusing is not final. You can reconsider it from the section below,
                      and nothing is written to the ledger either way. Only a release is.
                    </p>
                  </div>
                ) : (
                  <div className="areq__actions">
                    <button
                      type="button"
                      className="btn btn--primary btn--sm"
                      disabled={busy !== null || !pick}
                      onClick={() => {
                        void act(groupKey, async () => {
                          if (group.length === 1) return api.answerRequest(first.id, pick);
                          // Deliberately not all-or-nothing. If the contract
                          // refuses one column the others are still real
                          // permissions, and rolling them back would throw away
                          // access this factory meant to give.
                          const out = await api.answerBatch(ids, pick);
                          setPartial((prev) => ({
                            ...prev,
                            [groupKey]: out.failed.length
                              ? `${out.summary}. ${out.failed.map((f) => f.message).join(' ')}`
                              : '',
                          }));
                          return out;
                        });
                      }}
                    >
                      <KeyRound size={13} />
                      {working
                        ? 'Writing to the ledger…'
                        : group.length === 1
                          ? 'Release this figure'
                          : `Release all ${group.length}`}
                    </button>
                    {group.length === 1 && (
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        disabled={busy !== null}
                        onClick={() => { setDeclining(first.id); setReason(''); }}
                      >
                        Refuse
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/* -- 2. what you decided -------------------------------------------------- */
function Answered({
  requests, records, onDone,
}: {
  requests: AccessRequest[];
  records: LedgerRecord[];
  onDone: () => void;
}) {
  const labelOf = useFieldLabel();
  const { busy, failure, act } = useAction(onDone);
  const [reissuing, setReissuing] = useState<string | null>(null);
  const [chosen, setChosen] = useState<Record<string, string>>({});
  const [revoking, setRevoking] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  return (
    <section className="acc__section">
      <h2 className="acc__h2">Answered</h2>
      <p className="lead acc__lede">
        What you decided, and what became of it. The state on the right is read off
        the ledger rather than from the answer you gave. Access can be withdrawn
        long after the request that produced it was closed.
      </p>
      {failure && <Failed error={failure} />}

      {requests.length === 0 ? (
        <Empty title="Nothing answered yet" detail="Requests you grant or decline collect here." />
      ) : (
        <ul className="acc__list">
          {requests.map((r) => {
            const withdrawn = r.status === 'granted' && r.grant_status === 'revoked';
            const declined = r.status === 'declined';
            const candidates = records.filter(
              (x) => x.record_type === r.record_type && x.period === r.period,
            );
            const pick = chosen[r.id] ?? r.grant_record_id ?? candidates[0]?.record_id ?? '';

            return (
              <li key={r.id} className="areq areq--answered">
                <div className="areq__head">
                  <div>
                    <p className="areq__who">{shortMsp(r.requester_msp)}</p>
                    <p className="small areq__what">
                      <strong>{labelOf(r.record_type, r.field_name)}</strong> ·{' '}
                      {recordLabel(r.record_type)}, {period(r.period)} ·{' '}
                      <span>{purposeLabel(r.purpose_code)}</span>
                    </p>
                    {r.grant_record_id && (
                      <p className="small areq__when">
                        granted against{' '}
                        <Link
                          to={`/factory/records/${encodeURIComponent(r.grant_record_id)}`}
                          className="mono"
                        >
                          {r.grant_record_id}
                        </Link>{' '}
                        as <span className="mono">{r.grant_id}</span>
                      </p>
                    )}
                    {declined && r.decline_reason && (
                      <p className="small areq__reasontext">You said: {r.decline_reason}</p>
                    )}
                    {withdrawn && r.grant_revoked_reason && (
                      <p className="small areq__reasontext">
                        Withdrawn: {r.grant_revoked_reason}
                      </p>
                    )}
                  </div>
                  <Seal
                    tone={declined ? 'inert' : withdrawn ? 'broken' : 'sealed'}
                  >
                    {declined ? 'declined' : withdrawn ? 'withdrawn' : 'live'}
                  </Seal>
                </div>

                {/* Withdrawing access you granted. It belongs here as much as in
                    the table below: this is the row that says you said yes, so
                    it is where somebody looks to stop saying it. */}
                {!declined && !withdrawn && r.grant_id && (
                  revoking === r.id ? (
                    <div className="areq__reason">
                      <input
                        className="input"
                        placeholder="Why is this access being withdrawn?"
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                      />
                      <div className="areq__actions">
                        <button
                          type="button"
                          className="btn btn--danger btn--sm"
                          disabled={reason.trim().length < 4 || busy === r.id}
                          onClick={() => {
                            void act(r.id, () => api.revoke(r.grant_id!, reason.trim()))
                              .then((ok) => {
                                if (!ok) return;
                                setRevoking(null);
                                setReason('');
                              });
                          }}
                        >
                          {busy === r.id ? 'Revoking…' : 'Revoke, permanently'}
                        </button>
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm"
                          onClick={() => { setRevoking(null); setReason(''); }}
                        >
                          Cancel
                        </button>
                      </div>
                      <p className="small areq__note">
                        The reason goes on the ledger with your identity and is shown to
                        the buyer. Access can be issued again afterwards, as a new grant.
                      </p>
                    </div>
                  ) : (
                    <div className="areq__actions">
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        onClick={() => { setRevoking(r.id); setReason(''); }}
                      >
                        Revoke this access
                      </button>
                    </div>
                  )
                )}

                {declined && (
                  <div className="areq__actions">
                    <button
                      type="button"
                      className="btn btn--secondary btn--sm"
                      disabled={busy === r.id}
                      onClick={() => void act(r.id, () => api.reconsiderRequest(r.id))}
                    >
                      <Undo2 size={13} />
                      {busy === r.id ? 'Reopening…' : 'Reconsider'}
                    </button>
                    <p className="small areq__note">
                      Puts it back in <em>Awaiting you</em> as an open decision. Off the
                      ledger, like the request itself.
                    </p>
                  </div>
                )}

                {withdrawn && (
                  reissuing === r.id ? (
                    <div className="areq__reason">
                      <label className="areq__pick">
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
                      <div className="areq__actions">
                        <button
                          type="button"
                          className="btn btn--primary btn--sm"
                          disabled={busy === r.id || !pick}
                          onClick={() => {
                            void act(r.id, () => api.answerRequest(r.id, pick))
                              .then((ok) => ok && setReissuing(null));
                          }}
                        >
                          <KeyRound size={13} />
                          {busy === r.id ? 'Writing to the chain…' : 'Issue a new grant'}
                        </button>
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm"
                          onClick={() => setReissuing(null)}
                        >
                          Cancel
                        </button>
                      </div>
                      <p className="small areq__note">
                        The revoked grant stays where it is. This writes a second one, with
                        its own identifier, so the record shows access being given, taken
                        away and given again rather than a history that was tidied up.
                      </p>
                    </div>
                  ) : (
                    <div className="areq__actions">
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        disabled={candidates.length === 0}
                        onClick={() => setReissuing(r.id)}
                      >
                        <KeyRound size={13} /> Grant access again
                      </button>
                    </div>
                  )
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/* -- 3. what is live ------------------------------------------------------ */
function Issued({
  grants, records, onDone,
}: {
  grants: Grant[];
  records: LedgerRecord[];
  onDone: () => void;
}) {
  const { busy, failure, act } = useAction(onDone);
  const [status, setStatus] = useState('active');
  const [who, setWho] = useState('');
  const [query, setQuery] = useState('');
  const labelOf = useFieldLabel();
  const [shown, setShown] = useState(PAGE);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [reason, setReason] = useState('');

  const byId = new Map(records.map((r) => [r.record_id, r]));
  const buyers = [...new Set(grants.map((g) => g.requester_msp))].sort();

  const filtered = grants
    .filter(
      (g) =>
        (!status || g.status === status)
        && (!who || g.requester_msp === who)
        && (!query
          || g.record_id.toLowerCase().includes(query.toLowerCase())
          || g.field_name.toLowerCase().includes(query.toLowerCase())
          || g.grant_id.toLowerCase().includes(query.toLowerCase())),
    )
    // Newest first. The ledger returns key order, which puts the grant you
    // wrote a minute ago last — the one place a factory is certain to look for
    // it is the top.
    .sort((a, b) => b.granted_at.localeCompare(a.granted_at));

  return (
    <section className="acc__section">
      <h2 className="acc__h2">Grants you have issued</h2>
      <p className="lead acc__lede">
        Every one of them, live and ended. Each is one field of one document, and
        revoking it takes effect at the contract: a verification against a revoked
        grant is refused, not merely hidden.
      </p>
      {failure && <Failed error={failure} />}

      <div className="acc__filters">
        <label className="acc__pick">
          <span className="stamp-type">Status</span>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="active">Live</option>
            <option value="revoked">Revoked</option>
            <option value="">All</option>
          </select>
        </label>
        <label className="acc__pick">
          <span className="stamp-type">Holder</span>
          <select className="input" value={who} onChange={(e) => setWho(e.target.value)}>
            <option value="">Everyone</option>
            {buyers.map((b) => (
              <option key={b} value={b}>{shortMsp(b)}</option>
            ))}
          </select>
        </label>
        <label className="acc__search">
          <span className="stamp-type">Record, field or grant</span>
          <input
            className="input"
            type="search"
            value={query}
            placeholder="doc-… · net_pay_bdt · g-…"
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
      </div>

      <p className="small acc__count">
        {commas(filtered.length)} of {commas(grants.length)} grants.
      </p>

      {filtered.length === 0 ? (
        <Empty title="Nothing matches" detail="No grant you have issued fits those filters." />
      ) : (
        <>
          <div className="scroll-x">
            <table className="acctable">
              <thead>
                <tr>
                  <th scope="col">Record</th>
                  <th scope="col">Holder</th>
                  <th scope="col">Field</th>
                  <th scope="col">Purpose</th>
                  <th scope="col">Granted</th>
                  <th scope="col">Until</th>
                  <th scope="col">State</th>
                  <th scope="col"><span className="visually-hidden">Action</span></th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, shown).map((g) => {
                  const record = byId.get(g.record_id);
                  const open = revoking === g.grant_id;
                  return (
                    <tr key={g.grant_id} className={g.status === 'active' ? '' : 'is-ended'}>
                      <th scope="row">
                        <Link
                          to={`/factory/records/${encodeURIComponent(g.record_id)}`}
                          className="mono"
                        >
                          {g.record_id}
                        </Link>
                        {record && (
                          <span className="small dim acctable__sub">
                            {recordLabel(record.record_type)} · {period(record.period)} ·{' '}
                            {record.site}
                          </span>
                        )}
                      </th>
                      <td>{shortMsp(g.requester_msp)}</td>
                      <td>{labelOf(record?.record_type ?? '', g.field_name)}</td>
                      <td className="small">{purposeLabel(g.purpose_code)}</td>
                      <td className="mono dim">{longDate(g.granted_at)}</td>
                      <td className="mono dim">{longDate(g.expires_at)}</td>
                      <td>
                        <Seal tone={g.status === 'active' ? 'sealed' : 'broken'}>
                          {g.status}
                        </Seal>
                        {g.revoked_reason && (
                          <span className="small dim acctable__sub">{g.revoked_reason}</span>
                        )}
                      </td>
                      <td className="acctable__act">
                        {g.status !== 'active' ? null : open ? (
                          <div className="acctable__revoke">
                            <input
                              className="input"
                              placeholder="Why? This goes on the ledger."
                              value={reason}
                              onChange={(e) => setReason(e.target.value)}
                            />
                            <button
                              type="button"
                              className="btn btn--danger btn--sm"
                              disabled={reason.trim().length < 4 || busy === g.grant_id}
                              onClick={() => {
                                void act(g.grant_id, () => api.revoke(g.grant_id, reason.trim()))
                                  .then((ok) => {
                                    if (!ok) return;
                                    setRevoking(null);
                                    setReason('');
                                  });
                              }}
                            >
                              {busy === g.grant_id ? 'Revoking…' : 'Revoke, permanently'}
                            </button>
                            <button
                              type="button"
                              className="btn btn--ghost btn--sm"
                              onClick={() => { setRevoking(null); setReason(''); }}
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            className="btn btn--ghost btn--sm"
                            onClick={() => { setRevoking(g.grant_id); setReason(''); }}
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {shown < filtered.length && (
            <button
              type="button"
              className="btn btn--ghost acc__more"
              onClick={() => setShown((n) => n + PAGE)}
            >
              Show {Math.min(PAGE, filtered.length - shown)} more
            </button>
          )}
        </>
      )}
    </section>
  );
}

function Tally({ n, label, tone }: { n: number; label: string; tone: 'warn' | 'calm' }) {
  return (
    <div className={`atally atally--${tone}`}>
      <span className="atally__n">{commas(n)}</span>
      <span className="small atally__l">{label}</span>
    </div>
  );
}

/**
 * What was actually done with the access you gave.
 *
 * A grant is permission; a receipt is use. The two were never shown together —
 * receipts existed one record at a time on a record's own page, so a factory
 * could see that Primark held three hundred grants and had no way to learn
 * whether a single one had ever been exercised. The consortium's operations
 * page counted them and named none.
 *
 * The disclosed value is not here, and is not anywhere: it went to one
 * counterparty under a grant covering one field. What a receipt proves is that
 * a verification happened and which root it was checked against.
 */
function Verifications({ rows }: { rows: VerificationRow[] }) {
  const labelOf = useFieldLabel();
  const [shown, setShown] = useState(PAGE);

  return (
    <section className="acc__section">
      <h2 className="acc__h2">Verifications against your records</h2>
      <p className="lead acc__lede">
        Permission is one thing, use is another. This is use: every check anyone ran against a
        document of yours, with the field it covered and whether the root still
        matches what the ledger holds.
      </p>

      {rows.length === 0 ? (
        <Empty
          title="Nothing verified yet"
          detail="A receipt appears here the first time a counterparty proves a value against one of your records."
        />
      ) : (
        <>
          <div className="scroll-x">
            <table className="acctable">
              <thead>
                <tr>
                  <th scope="col">Record</th>
                  <th scope="col">Verified by</th>
                  <th scope="col">Field</th>
                  <th scope="col">Result</th>
                  <th scope="col">Root</th>
                  <th scope="col">When</th>
                  <th scope="col">Receipt</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, shown).map((r) => (
                  <tr key={r.receipt_id}>
                    <th scope="row">
                      <Link
                        to={`/factory/records/${encodeURIComponent(r.record_id)}`}
                        className="mono"
                      >
                        {r.record_id}
                      </Link>
                      <span className="small dim acctable__sub">
                        {recordLabel(r.record_type)} · {period(r.period)} · {r.site}
                      </span>
                    </th>
                    <td>{shortMsp(r.verifier_msp)}</td>
                    <td>{labelOf(r.record_type, r.field_name)}</td>
                    <td>
                      <Seal tone={r.result === 'match' ? 'sealed' : 'broken'}>
                        {r.result === 'match' ? 'matched' : 'no match'}
                      </Seal>
                    </td>
                    <td>
                      {r.root_matches ? (
                        <span className="small dim">unchanged since</span>
                      ) : (
                        <span className="small acctable__drift">
                          differs from the ledger now
                        </span>
                      )}
                    </td>
                    <td className="mono dim">{dateTime(r.verified_at)}</td>
                    <td>
                      <Link
                        to={`/verify/${encodeURIComponent(r.receipt_id)}`}
                        className="mono small"
                      >
                        {r.receipt_id}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {shown < rows.length && (
            <button
              type="button"
              className="btn btn--ghost acc__more"
              onClick={() => setShown((n) => n + PAGE)}
            >
              Show {Math.min(PAGE, rows.length - shown)} more
            </button>
          )}
        </>
      )}
    </section>
  );
}
