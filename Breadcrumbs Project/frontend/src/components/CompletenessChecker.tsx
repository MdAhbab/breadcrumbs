import { AlertTriangle, Check, Loader2, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import {
  ApiError, api, purposeLabel,
  type Completeness, type Grant, type LedgerRecord, type PeriodSeal,
} from '../lib/api';
import { commas, longDate, shortHash } from '../lib/format';
import { useFieldLabel } from '../lib/useFieldLabel';
import { Failed } from './states';
import { Tech } from './Tech';
import { Seal } from './ui';
import './mechanisms.css';
import './completeness.css';

/**
 * Was anything withheld?
 *
 * Other systems prove a record is genuine. This proves nothing is missing, and
 * the difference is the whole submission — so the screen shows the arithmetic
 * rather than a verdict. Sealed twenty-four, disclosed twenty-three, and two
 * roots that plainly are not the same string. Nobody has to be believed.
 *
 * Both roots come from the contract. An earlier version of this component
 * computed the "root of what you hold" in the browser with an xorshift, which
 * meant the most load-bearing screen in the product was showing a number it had
 * made up: it would have reported a mismatch for a disclosure that was in fact
 * complete, and nothing on the page would have said so.
 *
 * The list stays editable on purpose. Taking the withheld register out and
 * watching the roots diverge — with the answer coming from the ledger each time
 * — is a better demonstration of what a commitment does than any copy.
 *
 * What changed, and why the left column is no longer a wall of serial numbers:
 *
 * The identifiers are load-bearing as *data* — the sealed root is a hash over
 * those exact strings — and not load-bearing as *pixels*. The contract sorts
 * the set before hashing, so how this screen groups, filters or pages them
 * cannot move the answer. Twenty-eight ticked serials down the left of the page
 * therefore supported no task at all: nobody recognises a document by
 * `doc-ash-w2-008921`, the one real question ("do I hold this one?") is a
 * lookup rather than a scan, and the one question the list appears to answer
 * ("which am I missing?") is the one it provably cannot — a withheld record is
 * not in this array and never can be.
 *
 * So: a summary of what the set is, a search for the lookup, filters for the
 * facts that actually vary inside a month, and the identifiers still there in
 * full, because the mechanism commits to those strings and hiding them would be
 * hiding the evidence.
 */

type Filter = 'all' | 'provable' | 'unprovable' | 'signed' | 'excluded';

export function CompletenessChecker({
  seal,
  given,
  grants,
  readsEverything = false,
}: {
  seal: PeriodSeal;
  /** Every record of this period this caller can see. */
  given: LedgerRecord[];
  /** This caller's live permissions inside this period. */
  grants: Grant[];
  /**
   * True for an auditor, which reads every document on the channel by right
   * rather than by disclosure. Without this the check is a tautology: its "what
   * I was shown" is the whole sealed month by construction, so the panel could
   * only ever print "nothing is missing" — including for the period this world
   * seeds a withholding into.
   */
  readsEverything?: boolean;
}) {
  const ids = useMemo(() => given.map((r) => r.record_id).sort(), [given]);
  const [disclosed, setDisclosed] = useState<string[]>(ids);
  const [result, setResult] = useState<Completeness | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  // The list of documents, not the array holding it: the parent rebuilds that
  // on every render, so depending on the array itself would throw away the
  // reader's toggles the moment anything else on the page changed.
  const key = ids.join('|');
  useEffect(() => setDisclosed(ids.slice()), [key]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let live = true;
    setBusy(true);
    setError(null);
    api
      .completeness({
        owner_msp: seal.owner_msp,
        site: seal.site,
        record_type: seal.record_type,
        period: seal.period,
        disclosed_record_ids: [...new Set(disclosed)],
      })
      .then((r) => live && setResult(r))
      .catch((err: unknown) => {
        if (!live) return;
        setResult(null);
        setError(err instanceof ApiError ? err : new ApiError(0, 'the check failed'));
      })
      .finally(() => live && setBusy(false));
    return () => {
      live = false;
    };
  }, [disclosed, seal]);

  const toggle = (id: string) =>
    setDisclosed((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));

  // How many are missing is the ledger's arithmetic, not a count of what this
  // caller can see. A buyer holds only what it was given, so the withheld ids
  // are not in `given` and never can be — that asymmetry is the mechanism.
  // Counting locally produced "A records withheld" when the shortfall was 1.
  const shortfall = Math.max(
    0,
    (result?.sealed_count ?? 0) - (result?.disclosed_count ?? 0),
  );

  // Whether the reader has changed the set. Everything on the right is then an
  // answer about a set they invented, and it has to say so — otherwise taking a
  // row out makes the screen assert a withholding that never happened.
  const whatIf = disclosed.length !== ids.length;

  return (
    <div className="cchk">
      <Given
        given={given}
        grants={grants}
        disclosed={disclosed}
        onToggle={toggle}
        readsEverything={readsEverything}
      />

      {error ? (
        <Failed error={error} />
      ) : result === null ? (
        <div className="cchk__verdict">
          <div className="cchk__banner"><Loader2 size={18} /> <span>Asking the ledger…</span></div>
        </div>
      ) : !result.sealed ? (
        <div className="cchk__verdict is-short">
          <div className="cchk__banner">
            <AlertTriangle size={18} />
            <span>
              {result.status === 'reopened'
                ? 'This month was reopened and has not been closed again.'
                : 'This month has never been closed.'}
            </span>
          </div>
          <p className="cchk__reason">{result.reason}</p>
        </div>
      ) : (
        <div className={`cchk__verdict ${result.complete ? 'is-ok' : 'is-short'}`}>
          <div className="cchk__banner">
            {result.complete ? <Check size={18} strokeWidth={2.5} /> : <AlertTriangle size={18} />}
            <span>
              {result.complete
                ? readsEverything
                  ? 'Every document this month holds is one you can open.'
                  : 'Nothing is missing. You were shown everything this month holds.'
                : shortfall > 0
                  /* Not "held back from you". The mechanism proves a difference
                     between two counts; it does not prove intent, and the
                     paragraph three elements below already says so. */
                  ? `You were shown ${commas(result.disclosed_count ?? 0)}. `
                    + `This month was closed at ${commas(result.sealed_count ?? 0)}.`
                  : 'What you were shown does not match what this month holds.'}
            </span>
            {busy && <span className="small dim">rechecking…</span>}
          </div>

          {whatIf && (
            <p className="cchk__whatif">
              You have taken {commas(ids.length - disclosed.length)} out of the check. The
              ledger is answering about the {commas(disclosed.length)} still ticked, not
              about what you actually hold.
            </p>
          )}

          <div className="cchk__counts">
            <div>
              <span className="cchk__n">{result.sealed_count}</span>
              <span className="stamp-type">in the closed month</span>
            </div>
            <span className="cchk__vs" aria-hidden="true">/</span>
            <div>
              <span className="cchk__n">{result.disclosed_count}</span>
              <span className="stamp-type">{readsEverything ? 'you can open' : 'shown to you'}</span>
            </div>
          </div>

          {/* When the count was fixed, which is the whole force of the check
              and was only stated further down the page on another card. */}
          <p className="small cchk__when">
            Closed at {commas(seal.record_count)} record
            {seal.record_count === 1 ? '' : 's'} on {longDate(seal.sealed_at)}
            {seal.version > 1 && `, version ${seal.version}`} — before any of it was
            released.
          </p>

          <Tech>
            <div className="cchk__roots">
              <div className="cchk__root">
                <span className="stamp-type">Sealed root, on the ledger</span>
                <span className="mono">{shortHash(result.sealed_root ?? '')}</span>
              </div>
              <div className={`cchk__root ${result.complete ? '' : 'is-bad'}`}>
                <span className="stamp-type">Root of what you hold</span>
                <span className="mono">{shortHash(result.computed_root ?? '')}</span>
              </div>
            </div>
          </Tech>

          <p className="cchk__reason">
            {result.complete
              ? readsEverything
                /* An auditor reads the whole channel, so "nothing is missing"
                   is true of its access rather than of any disclosure. Saying
                   it the buyer's way would be the screen congratulating a
                   factory for a completeness it never had to demonstrate. */
                ? 'You read this month by right of audit rather than by disclosure, so this '
                  + 'confirms your own access rather than the factory’s openness. The '
                  + 'check bites where a document is released rather than read — a buyer '
                  + 'holding this period sees only what it was given.'
                : 'The month was closed at this exact list of records before you asked, and '
                  + 'what you hold is that list. Nothing was left out.'
              : `${result.reason}. The month says it holds more than you were shown. That is `
                + 'arithmetic, not an accusation.'}
          </p>

          {!result.complete && !readsEverything && (
            <p className="small cchk__cannot">
              Which one is missing is not something this page can tell you: you were never
              given it, so it has no name here. What is fixed is the count, and it was
              fixed before the disclosure was made.
            </p>
          )}

          {(result.amendment_count ?? 0) > 0 && (
            <p className="small cchk__amend">
              This month has been corrected {result.amendment_count} time
              {result.amendment_count === 1 ? '' : 's'}. Read the corrections before
              relying on the count.
            </p>
          )}

          <p className="small cchk__limit">
            What this cannot do: a file the factory never put on the ledger at all
            leaves everything here looking consistent. This catches things being held
            back from you. It does not prove the factory is honest.
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * What you hold, as something a person can read.
 *
 * The identifiers stay, in full, because the sealed root is a hash over exactly
 * those strings. What is new is everything around them: what the set adds up
 * to, a search for the only question anybody actually asks of it, and the two
 * facts that genuinely vary inside one month — how big each document is, and
 * whether an independent organisation counter-signed it. Site, kind and month
 * do not vary inside a bucket, so they are named once in the picker above and
 * never repeated here.
 */
function Given({
  given, grants, disclosed, onToggle, readsEverything,
}: {
  given: LedgerRecord[];
  grants: Grant[];
  disclosed: string[];
  onToggle: (id: string) => void;
  readsEverything: boolean;
}) {
  const fieldLabel = useFieldLabel();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [shown, setShown] = useState(10);

  useEffect(() => setShown(10), [query, filter]);

  const provable = new Set(grants.map((g) => g.record_id));
  const rows = given.reduce((n, r) => n + r.row_count, 0);
  const sizes = given.map((r) => r.row_count);
  const signed = given.filter((r) => r.witnesses.length > 0).length;
  const dates = [...new Set(given.map((r) => r.committed_at))].sort();
  const columns = [...new Set(grants.map((g) => g.field_name))]
    .map((f) => fieldLabel(given[0]?.record_type ?? '', f));
  const purposes = [...new Set(grants.map((g) => g.purpose_code))];

  // Only offer a filter for something that actually varies here. Three selects
  // each holding one option is the fault this page is being rescued from.
  const options: { id: Filter; label: string }[] = [
    { id: 'all', label: `All ${given.length}` },
    ...(provable.size > 0 && provable.size < given.length
      ? [
        { id: 'provable' as Filter, label: `Released to you (${provable.size})` },
        { id: 'unprovable' as Filter, label: `Read only (${given.length - provable.size})` },
      ]
      : []),
    ...(signed > 0 && signed < given.length
      ? [{ id: 'signed' as Filter, label: `Counter-signed (${signed})` }]
      : []),
    ...(disclosed.length < given.length
      ? [{
        id: 'excluded' as Filter,
        label: `Taken out (${given.length - disclosed.length})`,
      }]
      : []),
  ];

  const needle = query.trim().toLowerCase();
  const matching = given.filter((r) => {
    if (needle && !r.record_id.toLowerCase().includes(needle)) return false;
    if (filter === 'provable') return provable.has(r.record_id);
    if (filter === 'unprovable') return !provable.has(r.record_id);
    if (filter === 'excluded') return !disclosed.includes(r.record_id);
    if (filter === 'signed') return r.witnesses.length > 0;
    return true;
  });

  if (given.length === 0) {
    return (
      <div className="cchk__input">
        <p className="stamp-type cchk__label">What you were given</p>
        <p className="small cchk__hint">
          You hold no records in this period, so there is nothing to check against
          its seal.
        </p>
      </div>
    );
  }

  return (
    <div className="cchk__input">
      <p className="stamp-type cchk__label">
        {readsEverything ? 'What you can open' : 'What you were given'}
      </p>

      {/* The set in one line, from records the page already had in memory and
          was throwing away to keep only the identifiers. */}
      <p className="small cchk__summary">
        <strong>{commas(given.length)} document{given.length === 1 ? '' : 's'}</strong>
        {' · '}{commas(rows)} rows in all
        {sizes.length > 1 && `, ${commas(Math.min(...sizes))} to ${commas(Math.max(...sizes))} each`}
        {dates.length === 1
          ? ` · published ${longDate(dates[0])}`
          : ` · published between ${longDate(dates[0])} and ${longDate(dates[dates.length - 1])}`}
        {signed > 0 && ` · ${commas(signed)} counter-signed`}
      </p>

      {columns.length > 0 && (
        <p className="small cchk__released">
          Released to you as {columns.join(', ')}
          {purposes.length === 1 && `, ${purposeLabel(purposes[0]).toLowerCase()}`}.
        </p>
      )}

      <div className="cchk__tools">
        <label className="cchk__search">
          <span className="visually-hidden">Search these documents</span>
          <Search size={13} aria-hidden="true" />
          <input
            className="input"
            type="search"
            value={query}
            placeholder="Find an identifier…"
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        {options.length > 1 && (
          <select
            className="input cchk__filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value as Filter)}
            aria-label="Which of these to show"
          >
            {options.map((o) => (
              <option key={o.id} value={o.id}>{o.label}</option>
            ))}
          </select>
        )}
      </div>

      {matching.length === 0 ? (
        <p className="small cchk__hint">Nothing here matches that.</p>
      ) : (
        <>
          <ul className="cchk__list">
            {matching.slice(0, shown).map((r) => {
              const on = disclosed.includes(r.record_id);
              return (
                <li key={r.record_id}>
                  <button
                    type="button"
                    className={`cchk__item ${on ? 'is-on' : ''}`}
                    onClick={() => onToggle(r.record_id)}
                    aria-pressed={on}
                  >
                    <span className="cchk__box" aria-hidden="true">
                      {on && <Check size={12} strokeWidth={3} />}
                    </span>
                    <span className="mono cchk__id">{r.record_id}</span>
                    <span className="small cchk__rows">{commas(r.row_count)} rows</span>
                    {r.witnesses.length > 0 && <Seal tone="sealed">counter-signed</Seal>}
                    {/* Was "not disclosed", in red — a state a buyer's data can
                        never be in, since a withheld identifier is not in this
                        list at all. The only way to reach it is to press this
                        button, so it says what pressing it did. */}
                    {!on && <span className="small cchk__held">you took this out</span>}
                  </button>
                </li>
              );
            })}
          </ul>

          <div className="cchk__more">
            {matching.length > shown && (
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => setShown((n) => n + 20)}
              >
                Show {Math.min(20, matching.length - shown)} more
              </button>
            )}
            <p className="small cchk__hint">
              {matching.length < given.length
                ? `Showing ${commas(Math.min(shown, matching.length))} of `
                  + `${commas(matching.length)} that match. The check still uses all `
                  + `${commas(given.length)}.`
                : `Showing ${commas(Math.min(shown, matching.length))} of `
                  + `${commas(given.length)}.`}
              {' '}Take one out and the ledger recomputes the root. The seal was fixed
              when the month closed; nothing here can alter it.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
