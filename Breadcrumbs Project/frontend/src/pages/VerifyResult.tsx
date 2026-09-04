import { ArrowLeft, Check, Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { DocumentCheck } from '../components/DocumentCheck';
import { Result } from '../components/states';
import { Tech } from '../components/Tech';
import { Disclosure, LedgerRow, Seal } from '../components/ui';
import {
  api, recordLabel, shortMsp,
  type Grant, type LedgerRecord, type PublicReceipt,
} from '../lib/api';
import { commas, dateTime, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import { useFieldLabel } from '../lib/useFieldLabel';
import './verify.css';

/**
 * One object on a clean field.
 *
 * This is the product's thesis in one screen, and it is governed by the
 * five-second test: someone who does not know what a hash is must be able to
 * answer "is this genuine?" before they have finished arriving. So the verdict
 * is one plain sentence and every piece of cryptography is collapsed beneath a
 * disclosure. Nothing technical competes with the answer.
 *
 * Two ways in, and they are deliberately not the same:
 *
 *   * With a receipt identifier, and no account. Anyone can check that a
 *     disclosure was proved against the root its owner committed. The *value*
 *     is not shown, because it was released to one counterparty under a grant
 *     covering one field, and republishing it to anyone holding a receipt id
 *     would undo the disclosure model this whole product is about.
 *   * Signed in as the party that holds the grant. Then the proof is run live
 *     and the figure is on screen, because it was disclosed to you.
 *
 * The previous version showed a hardcoded value with a toggle that flipped
 * between a designed success and a designed failure. Both outcomes are still
 * reachable — but now by verifying something that passes and something that
 * does not.
 */
export default function VerifyResult() {
  const { id } = useParams();
  const { role } = useSession();
  return id ? <FromReceipt id={id} /> : <LiveProof signedIn={role !== null} />;
}

/**
 * Where "back" goes.
 *
 * This screen is reachable with an account and without one, and the way out
 * should match the way in. A visitor holding a receipt belongs on the landing
 * page; somebody signed in arrived from their own workspace and expects to be
 * returned to it rather than dropped on the page that explains the product to
 * strangers.
 */
function useWayBack(): { to: string; label: string } {
  const { role } = useSession();
  return role
    ? { to: role.landing, label: role.workspace }
    : { to: '/', label: 'Breadcrumbs' };
}

/* -- the public path ------------------------------------------------------ */
function FromReceipt({ id }: { id: string }) {
  const query = useApi(() => api.receipt(id), [id]);
  const back = useWayBack();
  const labelOf = useFieldLabel();

  return (
    <div className="lb">
      <header className="lb__bar">
        <Link to={back.to} className="lb__back"><ArrowLeft size={15} /> {back.label}</Link>
        <Link to="/verify" className="lb__toggle small">check something else</Link>
      </header>

      <main className="lb__main">
        <Result query={query} pendingLabel="Looking the receipt up on the ledger">
          {(data: PublicReceipt) => {
            const ok = data.root_matches && data.receipt.result === 'match';
            return (
              <>
                <div className={`verdictbar ${ok ? 'is-ok' : 'is-bad'}`}>
                  <span className="verdictbar__mark" aria-hidden="true">
                    {ok ? <Check size={20} strokeWidth={2.5} /> : <X size={20} strokeWidth={2.5} />}
                  </span>
                  <div>
                    <h1 className="verdictbar__head">
                      {ok
                        ? 'Checked. This value is real.'
                        : 'The check failed. Do not rely on this record.'}
                    </h1>
                    <p className="lead verdictbar__body">
                      {ok ? (
                        <>
                          The value was checked against the fingerprint{' '}
                          {data.record ? shortMsp(data.record.owner_msp) : 'the owner'} published
                          on {data.record ? longDate(data.record.committed_at) : 'the ledger'},
                          and it matches. Nothing has been altered since.
                        </>
                      ) : (
                        <>
                          The fingerprint on this receipt is not the one on the ledger.
                          Either the record or the receipt was altered after it was made.
                          Ask for it to be issued again, and do not treat this as evidence.
                        </>
                      )}
                    </p>
                  </div>
                </div>

                <section className="specimen">
                  <p className="stamp-type specimen__field">
                    {labelOf(data.record?.record_type ?? '', data.receipt.field_name)}
                  </p>
                  <p className="specimen__value specimen__value--withheld">disclosed privately</p>
                  <div className="specimen__seal">
                    <Seal tone={ok ? 'sealed' : 'broken'}>{ok ? 'Genuine' : 'Failed'}</Seal>
                  </div>
                  <p className="specimen__note small">{data.note}</p>
                </section>

                <div className="lb__detail">
                  <Disclosure summary="How this was checked" open>
                    <p className="small lb__explain">
                      The factory released one row, the random number it was mixed with,
                      and a handful of numbers from the tree above it. Whoever ran the
                      check worked the fingerprint out again from only those. This page
                      compares the answer they got with what is on the ledger now.
                    </p>

                    <div className={`proof ${ok ? '' : 'is-bad'}`}>
                      <div className="proof__side">
                        <p className="stamp-type">Worked out at the time of the check</p>
                        <p className="mono proof__hash">{data.receipt.computed_root}</p>
                      </div>
                      <div className="proof__verdict">
                        <span className={`proof__badge stamp-type ${ok ? 'ok' : 'bad'}`}>
                          {data.root_matches ? 'identical' : 'different'}
                        </span>
                      </div>
                      <div className="proof__side">
                        <p className="stamp-type">On the ledger now</p>
                        <p className="mono proof__hash">{data.on_chain_root ?? 'no such record'}</p>
                      </div>
                    </div>
                  </Disclosure>

                  <Disclosure summary="The receipt">
                    <div className="receipt">
                      <LedgerRow label="Receipt">
                        <span className="mono">{data.receipt.receipt_id}</span>
                      </LedgerRow>
                      <LedgerRow label="Checked by">{shortMsp(data.receipt.verifier_msp)}</LedgerRow>
                      <LedgerRow label="What was checked">
                        {labelOf(data.record?.record_type ?? '', data.receipt.field_name)}
                      </LedgerRow>
                      <LedgerRow label="Checked at">{dateTime(data.receipt.verified_at)}</LedgerRow>
                      <LedgerRow label="Result">
                        {data.receipt.result === 'match'
                          ? 'They match. The record is real.'
                          : 'They do not match. The check failed.'}
                      </LedgerRow>
                      {data.record && (
                        <>
                          <LedgerRow label="Record">
                            <span className="mono">{data.record.record_id}</span>
                          </LedgerRow>
                          <LedgerRow label="What it is">
                            {recordLabel(data.record.record_type)} · {period(data.record.period)} ·{' '}
                            {data.record.site}
                          </LedgerRow>
                          <LedgerRow label="Rows in the record">
                            {commas(data.record.row_count)}, of which one was released
                          </LedgerRow>
                        </>
                      )}
                      <LedgerRow label="Grant">
                        <span className="mono">{data.receipt.grant_id}</span>
                      </LedgerRow>
                    </div>
                  </Disclosure>

                  <Afterword />
                </div>
              </>
            );
          }}
        </Result>
      </main>
    </div>
  );
}

/* -- the signed-in path --------------------------------------------------- */
/** How many documents the picker lists before it asks to be told to go on. */
const PAGE = 12;

type Scope = 'held' | 'read' | 'all';

const SCOPES: { id: Scope; label: string }[] = [
  { id: 'held', label: 'Released to me' },
  { id: 'read', label: 'Read only' },
  { id: 'all', label: 'All' },
];

/**
 * The signed-in path: a document, and the proof that it is real.
 *
 * This screen used to be a form. It asked for a grant, then a row number, then
 * a column name, and returned one value. That is the shape of the API and not
 * the shape of anybody's question: nobody arrives wanting row 0 of anything.
 * A buyer opens what it was given, reads it, and wants to know whether it is
 * true — so the screen is now the document, with the check on every row of it.
 *
 * Rebuilt again, in the order the reader needs rather than the order the data
 * arrives in: which document and what you hold on it, then the document, then
 * what checking it leaves behind.
 *
 * The picker is the part that had to change twice. It was a `<select>`, which
 * is a fine control for five options and an unusable one for six hundred and
 * eighty-eight — an auditor reads every document on the network, so its list is
 * every document on the network, and finding one meant scrolling a native
 * dropdown past six hundred entries it had no permission to prove anything on.
 * It is now a card naming the current document, with a search-and-filter panel
 * behind one press. Closed by default: somebody arriving from a link is already
 * where they meant to be, and should not have to dismiss a chooser to read the
 * thing they chose.
 */
function LiveProof({ signedIn }: { signedIn: boolean }) {
  const back = useWayBack();
  const [params] = useSearchParams();
  const labelOf = useFieldLabel();

  // Everything this account can open. For a buyer that is what it holds
  // permissions on; for an auditor it is every document on the network.
  const records = useApi(
    () => (signedIn ? api.records() : Promise.resolve([] as LedgerRecord[])),
    [signedIn],
  );
  const grants = useApi(
    () => (signedIn ? api.grants() : Promise.resolve([] as Grant[])),
    [signedIn],
  );

  const [chosen, setChosen] = useState<string | null>(null);
  // The picker, and the two controls that make a list of hundreds usable.
  const [picking, setPicking] = useState(false);
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState<Scope>('held');
  const [listed, setListed] = useState(PAGE);

  // A link is an instruction, and it has to win over a choice made before it
  // arrived. Without this, opening one grant from the portal and then pressing
  // "see the number" on a second one left the first document on screen: the
  // route had not changed, only the query, so nothing re-mounted and the stale
  // selection stood. That is the whole of the reported bug — the page opened,
  // and opened the wrong thing.
  const link = `${params.get('grant') ?? ''}|${params.get('record') ?? ''}`;
  useEffect(() => { setChosen(null); setPicking(false); }, [link]);

  // Narrowing the list is a new question about it, so it starts from the top
  // rather than from wherever the last "show more" left off.
  useEffect(() => { setListed(PAGE); }, [query, scope]);

  if (!signedIn) {
    return (
      <div className="lb">
        <header className="lb__bar">
          <Link to={back.to} className="lb__back"><ArrowLeft size={15} /> {back.label}</Link>
        </header>
        <main className="lb__main">
          <div className="verdictbar">
            <div>
              <h1 className="verdictbar__head">Check a document.</h1>
              <p className="lead verdictbar__body">
                Opening a document needs an account, because what you can see depends on
                who you are. If somebody gave you a receipt link, you can check that one
                without signing in.
              </p>
            </div>
          </div>
          <section className="specimen">
            <div className="lb__after-actions">
              <Link to="/login" className="btn btn--primary btn--md">Sign in</Link>
            </div>
          </section>
          <div className="lb__detail"><Afterword /></div>
        </main>
      </div>
    );
  }

  return (
    <div className="lb">
      <header className="lb__bar">
        <Link to={back.to} className="lb__back"><ArrowLeft size={15} /> {back.label}</Link>
      </header>

      <main className="lb__main lb__main--wide">
        <Result query={records} pendingLabel="Reading what you can open">
          {(all: LedgerRecord[]) => {
            if (all.length === 0) {
              return (
                <div className="verdictbar">
                  <div>
                    <h1 className="verdictbar__head">Nothing to check yet.</h1>
                    <p className="lead verdictbar__body">
                      Nothing has been released to you, so there is no document to open.
                      Ask a factory for something first.
                    </p>
                  </div>
                </div>
              );
            }

            const live = (grants.data ?? []).filter((g) => g.status === 'active');
            const held = new Set(live.map((g) => g.record_id));

            // Which document the link is asking for. A grant identifier is the
            // usual way in — "see the number" on a permission names the
            // permission, not the file underneath it — so it is resolved to its
            // record here. `?record=` stays supported for links that already
            // know the document.
            const askedGrant = params.get('grant');
            const grantNamed = askedGrant
              ? (grants.data ?? []).find((g) => g.grant_id === askedGrant)
              : undefined;
            const wanted = grantNamed?.record_id ?? params.get('record') ?? null;
            const reachable = wanted && all.some((r) => r.record_id === wanted) ? wanted : null;
            // The link named something this account cannot open. Almost always
            // a permission that has since been withdrawn, and saying so is far
            // better than silently opening a different document.
            //
            // Only once the permissions have actually arrived, though: a grant
            // identifier cannot be resolved against a list that is still being
            // fetched, and flashing "the link you followed names something you
            // cannot open" for the half second before it lands would be the
            // screen accusing itself.
            const missed =
              !grants.loading
              && Boolean(askedGrant || params.get('record'))
              && !reachable;

            // Documents something has actually been released from come first,
            // because those are the ones that can be proved as well as read.
            const ordered = [...all].sort(
              (a, b) => Number(held.has(b.record_id)) - Number(held.has(a.record_id)),
            );
            const recordId = chosen ?? reachable ?? ordered[0].record_id;
            const record = all.find((r) => r.record_id === recordId) ?? ordered[0];
            const mine = live.filter((g) => g.record_id === record.record_id);
            const releasable = ordered.filter((r) => held.has(r.record_id));
            const readOnly = ordered.filter((r) => !held.has(r.record_id));

            // What the picker is showing. A search over the words actually on
            // the row — the month as it is written, the site, the kind of
            // document, the identifier — because those are what somebody has in
            // their hand when they come looking for one document out of 688.
            const pool = scope === 'held' ? releasable : scope === 'read' ? readOnly : ordered;
            const needle = query.trim().toLowerCase();
            const matching = needle
              ? pool.filter((r) =>
                [
                  recordLabel(r.record_type), period(r.period), r.period,
                  r.site, r.record_id, shortMsp(r.owner_msp),
                ].join(' ').toLowerCase().includes(needle))
              : pool;

            return (
              <>
                {/* One sentence. The three that were here explained the
                    Merkle check twice over before the reader had seen a single
                    row of the document they came to look at — and the same
                    explanation is on the table itself, where somebody deciding
                    whether to press the button is actually looking. */}
                <div className="verdictbar">
                  <div>
                    <h1 className="verdictbar__head">Verify a document.</h1>
                    <p className="lead verdictbar__body">
                      Read what was released to you, and check any row of it against the
                      fingerprint the factory published.
                    </p>
                  </div>
                </div>

                <div className="lb__detail">
                  {missed && (
                    <p className="lb__missed">
                      The link you followed names something you cannot open now. The usual
                      reason is that the permission behind it has been withdrawn — access
                      ends at the contract, so a link that worked yesterday stops working
                      rather than quietly showing you the file anyway. The document below
                      is one you do still hold.
                    </p>
                  )}

                  {/* Which document, what you hold on it, and the way to a
                      different one — one card rather than three stacked blocks
                      of prose. */}
                  <section className="docbar">
                    <div className="docbar__now">
                      <div className="docbar__what">
                        <p className="docbar__name">
                          {recordLabel(record.record_type)} · {period(record.period)} ·{' '}
                          {record.site}
                        </p>
                        <p className="small docbar__meta">
                          {shortMsp(record.owner_msp)} · published{' '}
                          {longDate(record.committed_at)}
                          <Tech> · <span className="mono">{record.record_id}</span></Tech>
                        </p>
                      </div>
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        onClick={() => setPicking((open) => !open)}
                        aria-expanded={picking}
                      >
                        <Search size={13} />
                        {picking ? 'Close' : 'Change document'}
                      </button>
                    </div>

                    {mine.length > 0 ? (
                      <ul className="docbar__held">
                        {mine.map((g) => (
                          <li key={g.grant_id} className="docbar__grant">
                            <Seal tone="sealed">
                              {labelOf(record.record_type, g.field_name)}
                            </Seal>
                            <span className="small docbar__until">
                              until {longDate(g.expires_at)}
                            </span>
                          </li>
                        ))}
                        <li className="small docbar__note">
                          Released to you, and provable. Everything else in the file is
                          readable at most.
                        </li>
                      </ul>
                    ) : (
                      <p className="small docbar__note">
                        Read only. Nothing in this document has been released to you, so
                        there is no row to prove — proving a figure writes a receipt naming
                        it, and that needs a permission.
                      </p>
                    )}

                    {picking && (
                      <div className="docpick">
                        <div className="docpick__controls">
                          <label className="docpick__search">
                            <span className="visually-hidden">Search documents</span>
                            <Search size={14} aria-hidden="true" />
                            <input
                              className="input"
                              type="search"
                              value={query}
                              placeholder="Month, site, kind of document, or identifier…"
                              onChange={(e) => setQuery(e.target.value)}
                              autoFocus
                            />
                          </label>
                          <div className="docpick__scopes" role="group" aria-label="Which documents">
                            {SCOPES.map(({ id, label }) => (
                              <button
                                key={id}
                                type="button"
                                className={`docpick__scope ${scope === id ? 'is-on' : ''}`}
                                aria-pressed={scope === id}
                                onClick={() => setScope(id)}
                              >
                                {label}
                                <span className="docpick__count">
                                  {commas(
                                    id === 'held' ? releasable.length
                                      : id === 'read' ? readOnly.length
                                        : ordered.length,
                                  )}
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>

                        {matching.length === 0 ? (
                          <p className="small docpick__none">
                            Nothing matches. {scope === 'held' && readOnly.length > 0
                              ? 'You may be looking at one you can read but hold nothing on — try "read only".'
                              : 'Try a month, a site, or part of an identifier.'}
                          </p>
                        ) : (
                          <>
                            <p className="small docpick__tally">
                              {matching.length === ordered.length
                                ? `${commas(matching.length)} documents`
                                : `${commas(matching.length)} of ${commas(ordered.length)} documents`}
                            </p>
                            <ul className="docpick__list">
                              {matching.slice(0, listed).map((r) => (
                                <li key={r.record_id}>
                                  <button
                                    type="button"
                                    className={`docpick__row ${
                                      r.record_id === record.record_id ? 'is-on' : ''}`}
                                    onClick={() => {
                                      setChosen(r.record_id);
                                      setPicking(false);
                                    }}
                                  >
                                    <span className="docpick__rowname">
                                      {recordLabel(r.record_type)} · {period(r.period)} ·{' '}
                                      {r.site}
                                    </span>
                                    <span className="small docpick__rowmeta">
                                      <span className="mono">{r.record_id}</span> ·{' '}
                                      {commas(r.row_count)} rows ·{' '}
                                      {shortMsp(r.owner_msp)}
                                    </span>
                                    <span className={`docpick__tag ${
                                      held.has(r.record_id) ? 'is-held' : ''}`}
                                    >
                                      {held.has(r.record_id)
                                        ? `${commas(
                                          live.filter((g) => g.record_id === r.record_id).length,
                                        )} released`
                                        : 'read only'}
                                    </span>
                                  </button>
                                </li>
                              ))}
                            </ul>
                            {matching.length > listed && (
                              <button
                                type="button"
                                className="btn btn--ghost btn--sm"
                                onClick={() => setListed((n) => n + PAGE)}
                              >
                                Show {Math.min(PAGE, matching.length - listed)} more
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </section>

                  {/* The document, and the check on each row. */}
                  <DocumentCheck key={record.record_id} recordId={record.record_id} />
                </div>

                {/* 4 — what checking leaves behind. Stated only where it is
                    true: with nothing released, nothing here writes a receipt,
                    and the page used to promise one either way. */}
                <footer className="lb__after">
                  <p className="lb__after-lede">
                    {mine.length > 0
                      ? 'A check writes a receipt anyone can verify without an account. Opening '
                        + 'the file writes nothing.'
                      : 'Opening a file writes nothing to the ledger. Only checking a released '
                        + 'figure does, and nothing here has been released to you.'}
                  </p>
                  <div className="lb__after-actions">
                    <Link to={back.to} className="btn btn--primary btn--md">
                      Back to {back.label}
                    </Link>
                  </div>
                </footer>
              </>
            );
          }}
        </Result>
      </main>
    </div>
  );
}

function Afterword() {
  const { role } = useSession();
  return (
    <footer className="lb__after">
      <p className="lb__after-lede">
        Anyone with the link can run this check. It needs no account, and it asks the
        factory for nothing.
      </p>
      <div className="lb__after-actions">
        {role ? (
          <Link to={role.landing} className="btn btn--primary btn--md">
            Back to {role.workspace}
          </Link>
        ) : (
          <>
            <Link to="/" className="btn btn--primary btn--md">What Breadcrumbs is</Link>
            <Link to="/login" className="btn btn--secondary btn--md">Sign in</Link>
          </>
        )}
      </div>
    </footer>
  );
}
