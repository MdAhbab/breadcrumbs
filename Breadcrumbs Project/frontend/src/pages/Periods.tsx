import { Search } from 'lucide-react';
import { useState } from 'react';

import { AbsenceProof } from '../components/AbsenceProof';
import { CompletenessChecker } from '../components/CompletenessChecker';
import { PeriodSealCard } from '../components/PeriodSealCard';
import { SealActions } from '../components/SealActions';
import { Empty, Failed, Result } from '../components/states';
import { Drawer, DrawerHead, PageHead } from '../components/ui';
import {
  ApiError, PURPOSE_LABEL, api, recordLabel, shortMsp,
  type Grant, type LedgerRecord, type Org, type PeriodSeal,
} from '../lib/api';
import { commas, longDate, period as periodName } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import './periods.css';

/**
 * Closed periods, and the question they exist to answer.
 *
 * A factory reads this as bookkeeping: which periods it has closed, at what
 * count, and how often it has had to reopen one. A buyer reads it as the
 * completeness check, which is the reason the seal exists at all — so for a
 * buyer the checker comes first and the seals are the evidence behind it.
 *
 * Note what a buyer's checklist contains: only the records it was actually
 * given. It cannot list the withheld ones, because it does not know them. The
 * shortfall is still visible, because the *count* was fixed on the ledger before
 * the disclosure was made. That asymmetry is the mechanism, and the screen would
 * be lying if it showed the buyer a tidy list of what it was missing.
 */
export default function Periods() {
  const { role } = useSession();
  const verifier = role?.id === 'buyer' || role?.id === 'auditor';
  const world = useApi(
    () => Promise.all([api.seals(), api.records(), api.grants(), api.orgs()]) as
      Promise<[PeriodSeal[], LedgerRecord[], Grant[], Org[]]>,
    [],
  );
  const [picked, setPicked] = useState<string | null>(null);

  return (
    <div className="periods">
      {/* "Check for gaps" named the fault rather than the job, and "Closed
          months" named the state a period ends in rather than the work of
          putting it there. Both now say what the person came to do: a buyer or
          an auditor is confirming a month is complete, and a factory is closing
          one, which is what every finance and compliance team already calls it. */}
      <PageHead
        eyebrow={verifier ? 'Monthly completeness' : `${role?.org} · month-end closing`}
        title={verifier ? 'Is this month complete?' : 'Month-end closing'}
        lede={
          verifier
            ? 'Proving one record is real is the easy half. This is the other one. A closed month has its list of records fixed before anybody asks about it, so if you are shown fewer than it says, that is arithmetic, not suspicion.'
            : 'Closing a month fixes exactly which records it contains. After that nothing can be slipped in quietly. A late record has to be added as an open correction, with a reason attached. Each of these opens its form in a panel at the right, with what it is about to do written out before you press.'
        }
      />

      <Result
        query={world}
        pendingLabel="Reading the closed months"
        /* Only a verifier has nothing to do here without a seal. A factory
           with records and no seals has the most to do of anyone — and this
           used to swallow the whole page, SealActions included, so the one
           screen that can close a period refused to render until a period had
           already been closed. */
        isEmpty={([seals]) => verifier && seals.length === 0}
        empty={{
          title: 'No closed months you can see',
          detail:
            'A month becomes visible to you once a factory has released something to '
            + 'you from a record inside it.',
        }}
      >
        {([seals, records, grants, orgs]) => {
          // The whole record, not only its identifier. The completeness check
          // needs the count and the identifiers; the person reading it needs to
          // know what the documents *are*, and the page already had that in
          // memory and was discarding it one line after fetching it.
          const recordsIn = (bucket: string) =>
            records
              .filter((r) => r.bucket === bucket)
              .sort((a, b) => a.record_id.localeCompare(b.record_id));
          const inBucket = (bucket: string) =>
            recordsIn(bucket).map((r) => r.record_id);

          const sealOf = new Map(seals.map((s) => [s.bucket, s]));

          // Every period this caller can see, closed or not.
          //
          // The picker was built from seals alone, so a record sealed into a
          // period that had never been closed — which is what sealing a record
          // for a new month produces — appeared nowhere on this page. It was in
          // the open-periods list at the foot of the screen the whole time, and
          // that is not the same as being findable. A verifier still sees only
          // sealed periods: an unsealed one has no count to check against, and
          // saying so is the honest answer rather than hiding the period.
          const buckets = verifier
            ? seals.map((s) => s.bucket)
            : [...new Set([...seals.map((s) => s.bucket), ...records.map((r) => r.bucket)])].sort();

          const label = (bucket: string) => {
            const seal = sealOf.get(bucket);
            const [, site, recordType, per] = bucket.split('|');
            const held = inBucket(bucket).length;
            // A reopened period's count is one the contract refuses to answer
            // with — its membership is mid-revision — so asserting a shortfall
            // from it here would contradict the panel below, which correctly
            // says the month is being corrected.
            const suffix = !seal
              ? ' · not closed yet'
              : seal.status === 'reopened' ? ' · being corrected'
                : held < seal.record_count ? ` · ${seal.record_count - held} missing` : '';
            return `${site} · ${recordLabel(recordType)} · ${periodName(per)}${suffix}`;
          };

          // Default to a period whose disclosure is short — the case worth
          // looking at. If none is, the first one will do.
          const short = seals.find((s) => inBucket(s.bucket).length < s.record_count);
          const currentBucket = buckets.find((b) => b === picked)
            ?? short?.bucket
            ?? buckets[0];
          const current = currentBucket ? sealOf.get(currentBucket) ?? null : null;

          if (!currentBucket) {
            return (
              <Empty
                title="Nothing to show yet"
                detail="Seal a record and the period it belongs to appears here."
              />
            );
          }

          return (
            <>
              {/* The factory comes here to close a month, so that is the first
                  thing on its page. It used to open on the verifier's
                  completeness checker, which for the owner of the records can
                  only ever say "complete" — and then on a wall of thirty
                  identical cards. Neither answered the question the person had
                  when they clicked "Closed months". */}
              {role?.id === 'factory' && (
                <section className="periods__section">
                  <SealActions records={records} seals={seals} onChange={world.reload} />
                </section>
              )}

              <section className="periods__section">
                <h2 className="periods__h2">
                  {verifier ? 'Check a month is complete' : 'Who holds a copy'}
                </h2>
                {!verifier && (
                  <p className="lead periods__lede">
                    Once a month is closed, this is who has been given something out of
                    it. Nobody else can see any of it.
                  </p>
                )}
                <div className="periods__picker">
                  <label className="periods__pick">
                    <span className="stamp-type">Period to check</span>
                    <select
                      className="input"
                      value={currentBucket}
                      onChange={(e) => setPicked(e.target.value)}
                    >
                      {buckets.map((b) => (
                        <option key={b} value={b}>{label(b)}</option>
                      ))}
                    </select>
                  </label>
                  {verifier && short && (
                    <p className="small periods__hint">
                      {seals.filter((s) => inBucket(s.bucket).length < s.record_count).length} of{' '}
                      {seals.length} periods you can see disclose fewer records than they
                      were sealed with.
                    </p>
                  )}

                </div>

                {/* The completeness check is a verifier's instrument, and only a
                    verifier's. Its two sets are "what the period holds" and
                    "what I was given", and for the owner of the records those
                    are the same set by construction, so run against a factory
                    it could only ever print "Complete", in second-person copy
                    written for somebody who had been given something.

                    Which put a green "Complete" on the factory's screen for the
                    exact period where the buyer's screen says a record was
                    withheld. Both numbers were right and the pair read as a
                    contradiction, because the factory's was answering a
                    question nobody had asked. The owner's question is who holds
                    this period, and that is the answer the buyer's shortfall
                    comes out of. */}
                {verifier && current ? (
                  <CompletenessChecker
                    key={current.bucket}
                    seal={current}
                    given={recordsIn(current.bucket)}
                    grants={grants.filter(
                      (g) => g.status === 'active'
                        && recordsIn(current.bucket).some((r) => r.record_id === g.record_id),
                    )}
                    /* An auditor reads every document on the channel, so its
                       "what I was shown" is the whole sealed month by
                       construction and the check could only ever print
                       "nothing is missing" — including on the period this
                       world seeds a withheld register into. Naming the
                       difference is the fix; pretending its read access is a
                       disclosure was the bug. */
                    readsEverything={role?.id === 'auditor'}
                  />
                ) : (
                  <WhoHolds
                    /* Remounted per period, the same reason the checker is.
                       Without it a refusal from one period stayed on screen
                       while a different one was being read, which is how a
                       stale "field required" ended up under a list nobody had
                       tried to disclose from. */
                    key={currentBucket}
                    bucket={currentBucket}
                    seal={current}
                    held={recordsIn(currentBucket)}
                    records={records}
                    grants={grants}
                    orgs={orgs}
                    onChange={world.reload}
                  />
                )}
              </section>

              <section className="periods__section">
                <h2 className="periods__h2">
                  {verifier ? 'The closed months behind that check' : 'Already closed'}
                </h2>
                {seals.length === 0 ? (
                  <Empty title="Nothing closed yet" />
                ) : verifier ? (
                  <div className="periods__grid">
                    {seals.map((s) => (
                      <PeriodSealCard key={s.bucket} seal={s} />
                    ))}
                  </div>
                ) : (
                  /* Thirty identical cards is not a list, it is a wall. The
                     factory scans this for two things: which months are closed,
                     and which ones it has had to correct. Both are one line. */
                  <ClosedList seals={seals} />
                )}
              </section>

              {role?.id === 'auditor' && (
                <section className="periods__section">
                  <h2 className="periods__h2">Proof of absence</h2>
                  <p className="lead periods__lede">
                    The operation no Merkle tree can perform. A certificate the ledger
                    never committed can be shown never to have been committed, rather
                    than merely not found.
                  </p>
                  <AbsenceProof />
                </section>
              )}
            </>
          );
        }}
      </Result>
    </div>
  );
}

/**
 * Every closed month, as a list rather than a wall.
 *
 * Thirty cards of identical shape is not a list, it is wallpaper: the factory
 * scans this for two things, which months are closed and which ones it has had
 * to correct, and both of those are one line each. The corrections are the part
 * worth looking at, so they are the only thing that expands.
 */
function ClosedList({ seals }: { seals: PeriodSeal[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const ordered = [...seals].sort((a, b) => b.bucket.localeCompare(a.bucket));

  return (
    <ul className="closed">
      {ordered.map((seal) => {
        const [, site, recordType, per] = seal.bucket.split('|');
        const corrections = seal.amendments.length;
        const expanded = open === seal.bucket;
        return (
          <li key={seal.bucket} className={`closed__row ${corrections ? 'has-fixes' : ''}`}>
            <div className="closed__main">
              <span className="closed__what">
                {recordLabel(recordType)} · {site}
              </span>
              <span className="closed__when">{periodName(per)}</span>
              <span className="small closed__count">
                {commas(seal.record_count)} record{seal.record_count === 1 ? '' : 's'}
              </span>
              {corrections > 0 ? (
                <button
                  type="button"
                  className="closed__fixes"
                  onClick={() => setOpen(expanded ? null : seal.bucket)}
                  aria-expanded={expanded}
                >
                  {corrections} correction{corrections === 1 ? '' : 's'}
                </button>
              ) : (
                <span className="small closed__clean">no corrections</span>
              )}
            </div>
            {expanded && (
              <ol className="closed__fixlist">
                {seal.amendments.map((a) => (
                  <li key={a.version}>
                    <p className="closed__fixreason">{a.reason}</p>
                    <p className="small closed__fixmeta">
                      {longDate(a.amended_at)} · was {a.previous_count} records ·
                      added {a.added.join(', ')}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * The tail of an identifier, as a name.
 *
 * A record has no title in this corpus — nothing but `doc-ash-w2-008882` — and
 * every document in one month shares its site, kind and period, so those cannot
 * tell two of them apart either. What is left that a person can hold in their
 * head is the last segment. The full identifier is always printed beside it,
 * because that is what the grants, the receipts and every other screen name.
 */
function shortRef(recordId: string): string {
  const tail = recordId.split('-').pop() ?? recordId;
  return `#${tail}`;
}

/**
 * The owner's side of the completeness check.
 *
 * A buyer recomputes the root over what it was given and compares it to the
 * count the factory sealed before the disclosure was made. This is the other
 * end of that arithmetic: how much of this period each counterparty actually
 * holds. Where a buyer is short, the number is here, with its name against it.
 *
 * Nothing new is fetched. A factory's `/api/grants` is every grant it has
 * issued, and the page already knows which records the period holds.
 */
/**
 * The owner's side of the completeness check.
 *
 * A buyer recomputes the root over what it was given and compares it to the
 * count the factory sealed before the disclosure was made. This is the other
 * end of that arithmetic: how much of this period each counterparty holds, and
 * which records went to nobody.
 *
 * An undisclosed record is a control rather than a label. Naming a gap and
 * offering no way to close it is the fault this codebase keeps finding in
 * itself — the reopened period with no amend button, the banner describing a
 * door that was not there — and a period nobody holds anything in is exactly
 * where a factory most needs to release something.
 */
function WhoHolds({
  bucket, seal, held, records, grants, orgs, onChange,
}: {
  bucket: string;
  /** Null while the period is still open: it holds records and has no count. */
  seal: PeriodSeal | null;
  /** Every record of this period, whole — not only its identifier. */
  held: LedgerRecord[];
  records: LedgerRecord[];
  grants: Grant[];
  orgs: Org[];
  onChange: () => void;
}) {
  const [, site, recordType, per] = bucket.split('|');
  const heldIds = held.map((r) => r.record_id);
  const inPeriod = new Set(heldIds);
  const typeOf = new Map(records.map((r) => [r.record_id, r.record_type]));

  // Who currently holds each record, and the same tallied by organisation.
  const holdersOf = new Map<string, string[]>();
  const live = new Map<string, number>();
  const ended = new Map<string, number>();
  for (const g of grants) {
    if (!inPeriod.has(g.record_id)) continue;
    if (g.status === 'active') {
      holdersOf.set(g.record_id, [...(holdersOf.get(g.record_id) ?? []), g.requester_msp]);
      live.set(g.requester_msp, (live.get(g.requester_msp) ?? 0) + 1);
    } else {
      ended.set(g.requester_msp, (ended.get(g.requester_msp) ?? 0) + 1);
    }
  }
  const holders = [...new Set([...live.keys(), ...ended.keys()])].sort();
  const undisclosed = heldIds.filter((id) => !holdersOf.has(id));
  const shared = held.length - undisclosed.length;

  // Terms to open the form with. This period first; failing that, any grant
  // this factory has issued on the same kind of record, which is where the
  // field name and purpose code for a chemical inventory or a safety
  // inspection actually live. Failing both, the form starts empty and is
  // filled in — a period nobody holds anything in has nothing to copy, and
  // that was the case with no control at all.
  const counterparties = orgs.filter((o) => !o.is_you && o.on_document_channel);
  const sameType = grants.filter((g) => typeOf.get(g.record_id) === recordType);
  const sibling = grants.find((g) => inPeriod.has(g.record_id) && g.status === 'active')
    ?? sameType.find((g) => g.status === 'active')
    ?? sameType[0];

  const [opening, setOpening] = useState<string | null>(null);
  // Twenty-eight rows of `doc-ash-w2-008882` with no way to narrow them is a
  // filing cabinet with the labels facing the wall. The identifier stays — it
  // is the handle everything else in the product refers to — but it stops
  // being the only thing on the row, and it stops being the only way in.
  const [query, setQuery] = useState('');
  const [only, setOnly] = useState<'all' | 'shared' | 'unshared'>('all');
  const [shownRecords, setShownRecords] = useState(12);
  const [parties, setParties] = useState<string[]>(
    () => (sibling?.requester_msp ? [sibling.requester_msp] : []),
  );
  // The columns this kind of record actually has, so the factory picks from
  // what is in the file rather than typing a name from memory.
  const columns = useApi(() => api.recordFields(), []);
  const shareable = (columns.data?.[recordType ?? ''] ?? []).filter((f) => f.requestable);
  const blockedFields = (columns.data?.[recordType ?? ''] ?? []).filter((f) => !f.requestable);
  const [partial, setPartial] = useState<string | null>(null);

  const [fields, setFields] = useState<string[]>(() =>
    sibling?.field_name ? [sibling.field_name] : []);
  const [purpose, setPurpose] = useState(() => sibling?.purpose_code ?? '');
  const [until, setUntil] = useState(() => (sibling?.expires_at ?? '2028-12-31').slice(0, 10));
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const ready = parties.length > 0 && fields.length > 0 && purpose.trim() !== '' && until !== '';

  /**
   * Share one record with everyone selected, one column at a time.
   *
   * A permission covers exactly one column for exactly one organisation, and
   * that does not change: it is the guarantee. What changed is that releasing
   * the same figure to a buyer and an auditor, or releasing three figures to
   * one buyer, is now one action rather than six trips through this form.
   *
   * Deliberately not all-or-nothing. If the contract refuses one pairing the
   * others are real permissions, and rolling them back would take away access
   * the factory meant to give. The form says exactly which failed and why.
   */
  const disclose = async (recordId: string) => {
    setBusy(true);
    setFailure(null);
    setPartial(null);

    const pairs = parties.flatMap((msp) => fields.map((name) => ({ msp, name })));
    const failed: string[] = [];
    let written = 0;

    for (const pair of pairs) {
      try {
        await api.grant({
          record_id: recordId,
          requester_msp: pair.msp,
          purpose_code: purpose.trim(),
          field_name: pair.name,
          expires_at: `${until}T00:00:00Z`,
        });
        written += 1;
      } catch (err) {
        const why = err instanceof ApiError ? err.message : 'it was refused';
        failed.push(`${shortMsp(pair.msp)} · ${pair.name}: ${why}`);
      }
    }

    setBusy(false);
    if (failed.length === 0) {
      setOpening(null);
      setPartial(null);
    } else {
      setPartial(
        `${written} of ${pairs.length} released. ${failed.join(' ')}`,
      );
    }
    onChange();
  };

  const toggleParty = (msp: string) =>
    setParties((c) => (c.includes(msp) ? c.filter((x) => x !== msp) : [...c, msp]));
  const toggleField = (name: string) =>
    setFields((c) => (c.includes(name) ? c.filter((x) => x !== name) : [...c, name]));

  return (
    <div className="whoholds">
      <div className="whoholds__records">
        <p className="stamp-type whoholds__label">What this month holds</p>
        {/* Red is for an asymmetry, not for a state.
            A month where nobody holds anything is simply unshared, and every
            row of it used to come out in the same red as a genuinely missing
            record — so a factory that had shared nothing was shown twenty-eight
            errors. The colour is now reserved for the case it was written for:
            some of this month went out and this record did not. */}
        <p className="small whoholds__summary">
          {shared === 0
            ? `${commas(held.length)} record${held.length === 1 ? '' : 's'}, none shared with anyone yet.`
            : `${commas(held.length)} record${held.length === 1 ? '' : 's'}, ${commas(shared)} shared.`}
        </p>

        <div className="whoholds__tools">
          <label className="whoholds__search">
            <span className="visually-hidden">Find a document</span>
            <Search size={13} aria-hidden="true" />
            <input
              className="input"
              type="search"
              value={query}
              placeholder="Find by reference…"
              onChange={(e) => { setQuery(e.target.value); setShownRecords(12); }}
            />
          </label>
          {shared > 0 && shared < held.length && (
            <select
              className="input whoholds__filter"
              value={only}
              onChange={(e) => {
                setOnly(e.target.value as 'all' | 'shared' | 'unshared');
                setShownRecords(12);
              }}
              aria-label="Which of these to show"
            >
              <option value="all">All {commas(held.length)}</option>
              <option value="shared">Shared ({commas(shared)})</option>
              <option value="unshared">Not shared ({commas(held.length - shared)})</option>
            </select>
          )}
        </div>

        {(() => {
          const needle = query.trim().toLowerCase();
          const matching = held.filter((r) => {
            if (needle && !r.record_id.toLowerCase().includes(needle)) return false;
            const to = holdersOf.get(r.record_id) ?? [];
            if (only === 'shared') return to.length > 0;
            if (only === 'unshared') return to.length === 0;
            return true;
          });

          if (matching.length === 0) {
            return <p className="small whoholds__note">Nothing here matches that.</p>;
          }

          return (
            <>
              <ul className="whoholds__ids">
                {matching.slice(0, shownRecords).map((r) => {
                  const to = holdersOf.get(r.record_id) ?? [];
                  return (
                    <li key={r.record_id} className="whoholds__id">
                      <span className="whoholds__doc">
                        {/* A name, then the reference. There is no title on a
                            record — the corpus has none — so the name is what
                            genuinely distinguishes one from the next: what kind
                            of document it is, its short reference, and how big
                            it is. The full identifier stays underneath, because
                            it is what every other screen and every grant names. */}
                        <span className="whoholds__docname">
                          {recordLabel(r.record_type)} {shortRef(r.record_id)}
                        </span>
                        <span className="small whoholds__docmeta">
                          <span className="mono">{r.record_id}</span> ·{' '}
                          {commas(r.row_count)} rows
                          {r.witnesses.length > 0 && ' · counter-signed'}
                          {r.status === 'superseded' && ' · corrected by a later version'}
                        </span>
                      </span>
                      {to.length > 0 ? (
                        <span className="small whoholds__to">
                          {to.length === 1 ? shortMsp(to[0]) : `${to.length} holders`}
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="whoholds__disclose small"
                          onClick={() => {
                            setFailure(null);
                            setPartial(null);
                            setOpening(r.record_id);
                          }}
                        >
                          share this one
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>

              {matching.length > shownRecords && (
                <button
                  type="button"
                  className="btn btn--ghost btn--sm whoholds__more"
                  onClick={() => setShownRecords((n) => n + 20)}
                >
                  Show {Math.min(20, matching.length - shownRecords)} more
                </button>
              )}
              {matching.length < held.length && (
                <p className="small whoholds__note">
                  {commas(matching.length)} of {commas(held.length)} shown. The month is
                  still closed at {commas(seal ? seal.record_count : held.length)}
                  {' '}whatever this list is filtered to.
                </p>
              )}
            </>
          );
        })()}

        {failure && <Failed error={failure} />}

        <p className="small whoholds__note">
          Every record the ledger holds for this period, and who you released each one
          to. This list is yours alone. A buyer sees only what it was given, which is
          why it can prove a record is missing without ever learning which.
        </p>
      </div>

      <div className="whoholds__panel">
        <p className="stamp-type whoholds__head">Who holds this period</p>
        <p className="whoholds__count">
          <span className="whoholds__n">{commas(seal ? seal.record_count : held.length)}</span>
          <span className="small">
            {seal ? (
              <>
                sealed into {recordLabel(recordType)}, {periodName(per)} · {site} ·{' '}
                version {seal.version}
              </>
            ) : (
              <>
                records in {recordLabel(recordType)}, {periodName(per)} · {site} ·{' '}
                <strong>not closed yet</strong>
              </>
            )}
          </span>
        </p>

        {!seal && (
          <p className="small whoholds__note">
            This period holds records and has never been closed, so there is no count
            fixed for anyone to check a disclosure against. Until it is closed a record
            can still be added to it quietly. Closing it is at the foot of this page,
            under <em>Open periods</em>.
          </p>
        )}

        {holders.length === 0 ? (
          <p className="small whoholds__note">
            No counterparty holds a grant against anything in this period.
            {seal
              ? ' It is closed and nothing was released, which is a complete answer. The '
                + 'exists so a disclosure can be checked against it later, not because '
                + 'one has to be made.'
              : ' Nothing has been released from it and it has not been closed.'}
          </p>
        ) : (
          <ul className="whoholds__list">
            {holders.map((msp) => {
              const n = live.get(msp) ?? 0;
              // Measured against the sealed count where there is one, and
              // against what the ledger holds today where there is not.
              const total = seal ? seal.record_count : held.length;
              const short = total - n;
              const revoked = ended.get(msp) ?? 0;
              return (
                <li key={msp} className={`whoholds__row ${short > 0 ? 'is-short' : ''}`}>
                  <span className="whoholds__who">{shortMsp(msp)}</span>
                  <span className="mono whoholds__of">
                    {commas(n)} of {commas(seal ? seal.record_count : held.length)}
                  </span>
                  <span className="small whoholds__gap">
                    {short > 0
                      ? `${commas(short)} never disclosed to them`
                      : 'holds the whole period'}
                    {revoked > 0 && ` · ${commas(revoked)} revoked`}
                  </span>
                </li>
              );
            })}
          </ul>
        )}

        <p className="small whoholds__note">
          A buyer checking this period has the ledger recompute the root over what it
          was given, and compares it to the count you fixed when you closed it.
          Where it is short, the two roots differ and the shortfall is arithmetic rather
          than an accusation. That is the same fact as this screen, seen from the other
          end.
          {undisclosed.length > 0 && undisclosed.length < held.length && (
            <>
              {' '}Here that shortfall is{' '}
              <span className="mono">{undisclosed.join(', ')}</span>.
            </>
          )}
        </p>
      </div>

      {opening && (
        <Drawer
          label={`Share ${opening}`}
          onClose={() => { setOpening(null); setPartial(null); }}
        >
          <DrawerHead
            eyebrow={`${recordLabel(recordType)} · ${periodName(per)} · ${site}`}
            title={`Share ${shortRef(opening)}`}
            onClose={() => { setOpening(null); setPartial(null); }}
          />

          <div className="whoholds__form">
            <p className="small">
              <span className="mono">{opening}</span> · {commas(
                held.find((r) => r.record_id === opening)?.row_count ?? 0,
              )} rows. Tick everyone who should get it and every figure they should see.
              Each figure goes to each organisation as its own permission, which you can
              withdraw one at a time.
            </p>

            <fieldset className="whoholds__set">
              <legend className="stamp-type">Share with</legend>
              <div className="whoholds__grid">
                {counterparties.map((o) => (
                  <label key={o.msp_id} className="whoholds__tick">
                    <input
                      type="checkbox"
                      checked={parties.includes(o.msp_id)}
                      onChange={() => toggleParty(o.msp_id)}
                    />
                    <span>{o.name}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <fieldset className="whoholds__set">
              <legend className="stamp-type">Which figures</legend>
              <div className="whoholds__grid">
                {shareable.map((f) => (
                  <label key={f.name} className="whoholds__tick">
                    <input
                      type="checkbox"
                      checked={fields.includes(f.name)}
                      onChange={() => toggleField(f.name)}
                    />
                    <span>{f.label}</span>
                  </label>
                ))}
              </div>
              {blockedFields.length > 0 && (
                <p className="small whoholds__blocked">
                  {blockedFields.map((f) => f.label).join(', ')} cannot be shared with
                  anyone. Those identify a person.
                </p>
              )}
            </fieldset>

            <div className="whoholds__pair">
              <label className="whoholds__field">
                <span className="stamp-type">What for</span>
                <select
                  className="input"
                  value={purpose}
                  onChange={(e) => setPurpose(e.target.value)}
                >
                  {Object.entries(PURPOSE_LABEL).map(([code, label]) => (
                    <option key={code} value={code}>{label}</option>
                  ))}
                </select>
              </label>
              <label className="whoholds__field">
                <span className="stamp-type">Until</span>
                <input
                  className="input"
                  type="date"
                  value={until}
                  onChange={(e) => setUntil(e.target.value)}
                />
              </label>
            </div>

            {parties.length > 0 && fields.length > 0 && (
              <p className="small whoholds__tally">
                {parties.length * fields.length} permission
                {parties.length * fields.length === 1 ? '' : 's'}:{' '}
                {fields.length} figure{fields.length === 1 ? '' : 's'} to{' '}
                {parties.length} organisation{parties.length === 1 ? '' : 's'}.
              </p>
            )}

            {partial && <p className="small whoholds__partial">{partial}</p>}
            {failure && <Failed error={failure} />}

            <div className="whoholds__formrow">
              <button
                type="button"
                className="btn btn--primary btn--sm"
                disabled={busy || !ready}
                onClick={() => void disclose(opening)}
              >
                {busy
                  ? 'Writing to the ledger…'
                  : ready
                    ? `Share ${parties.length * fields.length} permission`
                      + (parties.length * fields.length === 1 ? '' : 's')
                    : 'Share'}
              </button>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => { setOpening(null); setPartial(null); }}
              >
                Cancel
              </button>
            </div>

            <p className="small whoholds__note">
              {sibling
                ? 'Prefilled from the terms this kind of record was released on before. '
                : ''}
              Sharing writes a permission onto the ledger, which is the only thing
              sharing ever is here.
              {seal ? (
                <>
                  {' '}Closing does not move. It fixed this month at{' '}
                  {commas(seal.record_count)} before any of it was released, and that is
                  what makes the buyer&rsquo;s check mean anything.
                </>
              ) : (
                <>
                  {' '}This period is not closed, so a buyer receiving it has no fixed
                  count to check the disclosure against. Close it first if that check is
                  the point.
                </>
              )}
            </p>
          </div>
        </Drawer>
      )}
    </div>
  );
}
