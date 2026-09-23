import { Search } from 'lucide-react';
import { useState } from 'react';

import { AbsenceProof } from '../components/AbsenceProof';
import { CompletenessChecker } from '../components/CompletenessChecker';
import { SealActions } from '../components/SealActions';
import { Tech } from '../components/Tech';
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
        eyebrow={role?.org ?? ''}
        title={verifier ? 'Monthly completeness' : 'Month-end closing'}
        lede={
          verifier
            ? 'Check that you were shown every document in a closed month.'
            : 'Closing a month fixes how many documents it holds. A late document shows as a correction.'
        }
      />

      <Result
        query={world}
        pendingLabel="Loading months"
        /* Only a verifier has nothing to do here without a seal. A factory
           with records and no seals has the most to do of anyone — and this
           used to swallow the whole page, SealActions included, so the one
           screen that can close a period refused to render until a period had
           already been closed. */
        isEmpty={([seals]) => verifier && seals.length === 0}
        empty={{
          title: 'No closed months yet',
          detail: 'You see a month once a factory shares a document from it.',
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
                detail="Upload a document and its month shows here."
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
                  {verifier ? 'Check a month' : 'Who can see each month'}
                </h2>
                <div className="periods__picker">
                  <label className="periods__pick">
                    <span className="stamp-type">Month</span>
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
                      {seals.length} months are missing documents.
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
                <h2 className="periods__h2">Closed months</h2>
                {seals.length === 0 ? (
                  <Empty title="Nothing closed yet" />
                ) : (
                  /* Thirty identical cards is not a list, it is a wall, and a
                     buyer or auditor scanned them for the same two things the
                     factory does: which months are closed, and which ones were
                     corrected. Both are one line, for everyone. */
                  <ClosedList seals={seals} />
                )}
              </section>

              {role?.id === 'auditor' && (
                <section className="periods__section">
                  <h2 className="periods__h2">Check a certificate was never issued</h2>
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
  // Newest month first. Sorting the bucket string sorted by site, so a
  // September sat between two Mays.
  const ordered = [...seals].sort(
    (a, b) => b.period.localeCompare(a.period) || a.bucket.localeCompare(b.bucket),
  );

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
                {commas(seal.record_count)} document{seal.record_count === 1 ? '' : 's'}
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
                <span className="small closed__clean" />
              )}
            </div>
            {expanded && (
              <ol className="closed__fixlist">
                {seal.amendments.map((a) => (
                  <li key={a.version}>
                    <p className="closed__fixreason">{a.reason}</p>
                    <p className="small closed__fixmeta">
                      {longDate(a.amended_at)} · was {a.previous_count} documents
                      <Tech> · added {a.added.join(', ')}</Tech>
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
            ? `${commas(held.length)} document${held.length === 1 ? '' : 's'}, none shared yet.`
            : `${commas(held.length)} document${held.length === 1 ? '' : 's'}, ${commas(shared)} shared.`}
        </p>

        <div className="whoholds__tools">
          <label className="whoholds__search">
            <span className="visually-hidden">Find a document</span>
            <Search size={13} aria-hidden="true" />
            <input
              className="input"
              type="search"
              value={query}
              placeholder="Find a document…"
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
                          {commas(r.row_count)} rows
                          {r.witnesses.length > 0 && ' · counter-signed'}
                          {r.status === 'superseded' && ' · replaced by a newer version'}
                          <Tech> · <span className="mono">{r.record_id}</span></Tech>
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
                  {commas(matching.length)} of {commas(held.length)} shown.
                </p>
              )}
            </>
          );
        })()}

        {failure && <Failed error={failure} />}

      </div>

      <div className="whoholds__panel">
        <p className="stamp-type whoholds__head">Who can see this month</p>
        <p className="whoholds__count">
          <span className="whoholds__n">{commas(seal ? seal.record_count : held.length)}</span>
          <span className="small">
            {seal ? (
              <>
                documents in {recordLabel(recordType)}, {periodName(per)} · {site}
                <Tech> · version {seal.version}</Tech>
              </>
            ) : (
              <>
                documents in {recordLabel(recordType)}, {periodName(per)} · {site} ·{' '}
                <strong>not closed yet</strong>
              </>
            )}
          </span>
        </p>

        {!seal && (
          <p className="small whoholds__note">
            Not closed yet, so buyers cannot check it is complete. Close it above.
          </p>
        )}

        {holders.length === 0 ? (
          <p className="small whoholds__note">Nobody can see anything from this month yet.</p>
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
                      ? `${commas(short)} not shared with them`
                      : 'can see the whole month'}
                    {revoked > 0 && ` · ${commas(revoked)} withdrawn`}
                  </span>
                </li>
              );
            })}
          </ul>
        )}

        {undisclosed.length > 0 && undisclosed.length < held.length && (
          <p className="small whoholds__note">
            A buyer checking this month will see {commas(undisclosed.length)} missing.
            <Tech> <span className="mono">{undisclosed.join(', ')}</span></Tech>
          </p>
        )}
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
              Tick who should get it and which figures they see.
              <Tech> <span className="mono">{opening}</span></Tech>
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
                  {blockedFields.map((f) => f.label).join(', ')} name a person and cannot
                  be shared.
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
                  ? 'Sharing…'
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

            {(sibling || !seal) && (
              <p className="small whoholds__note">
                {sibling ? 'Filled in from the last time you shared this type. ' : ''}
                {!seal && 'This month is not closed yet, so buyers cannot check it is complete.'}
              </p>
            )}
          </div>
        </Drawer>
      )}
    </div>
  );
}
