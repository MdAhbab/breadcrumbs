import { useState } from 'react';

import { AbsenceProof } from '../components/AbsenceProof';
import { CompletenessChecker } from '../components/CompletenessChecker';
import { PeriodSealCard } from '../components/PeriodSealCard';
import { SealActions } from '../components/SealActions';
import { Empty, Failed, Result } from '../components/states';
import { PageHead } from '../components/ui';
import {
  ApiError, api, recordLabel, shortMsp,
  type Grant, type LedgerRecord, type Org, type PeriodSeal,
} from '../lib/api';
import { commas, period as periodName } from '../lib/format';
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
      <PageHead
        eyebrow={verifier ? 'Completeness' : `${role?.org} · closed periods`}
        title={verifier ? 'Was anything withheld?' : 'Closed periods'}
        lede={
          verifier
            ? 'Other systems prove a record is genuine. A sealed period proves nothing is missing — the count and the root were fixed before you asked, so a short disclosure is arithmetic, not suspicion.'
            : 'Closing a period fixes exactly which records it holds. After that a late record cannot be slipped in quietly; it has to be an amendment, with a reason, in the open.'
        }
      />

      <Result
        query={world}
        pendingLabel="Reading the seals"
        /* Only a verifier has nothing to do here without a seal. A factory
           with records and no seals has the most to do of anyone — and this
           used to swallow the whole page, SealActions included, so the one
           screen that can close a period refused to render until a period had
           already been closed. */
        isEmpty={([seals]) => verifier && seals.length === 0}
        empty={{
          title: 'No sealed periods you can see',
          detail:
            'A period becomes visible to you once you hold a live grant against a '
            + 'record inside it.',
        }}
      >
        {([seals, records, grants, orgs]) => {
          const inBucket = (bucket: string) =>
            records.filter((r) => r.bucket === bucket).map((r) => r.record_id).sort();

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
            const suffix = !seal
              ? ' — not closed yet'
              : held < seal.record_count ? ` — short by ${seal.record_count - held}` : '';
            return `${site} · ${recordLabel(recordType)} · ${periodName(per)}${suffix}`;
          };

          // Default to a period whose disclosure is short — the case worth
          // looking at. If none is, the first one will do.
          const short = seals.find((s) => inBucket(s.bucket).length < s.record_count);
          const currentBucket = buckets.find((b) => b === picked)
            ?? short?.bucket
            ?? buckets[0];
          const current = currentBucket ? sealOf.get(currentBucket) ?? null : null;
          const unsealed = buckets.filter((b) => !sealOf.has(b));

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
              <section className="periods__section">
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
                  {!verifier && unsealed.length > 0 && (
                    <p className="small periods__hint">
                      {unsealed.length} period{unsealed.length === 1 ? '' : 's'} hold records
                      and {unsealed.length === 1 ? 'has' : 'have'} never been closed. Closing
                      one is at the foot of this page.
                    </p>
                  )}
                </div>

                {/* The completeness check is a verifier's instrument, and only a
                    verifier's. Its two sets are "what the period holds" and
                    "what I was given", and for the owner of the records those
                    are the same set by construction — so run against a factory
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
                    sealedIds={inBucket(current.bucket)}
                    disclosedIds={inBucket(current.bucket)}
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
                    held={inBucket(currentBucket)}
                    records={records}
                    grants={grants}
                    orgs={orgs}
                    onChange={world.reload}
                  />
                )}
              </section>

              {role?.id === 'factory' && (
                <section className="periods__section">
                  <h2 className="periods__h2">Close or reopen a period</h2>
                  <p className="lead periods__lede">
                    Closing a period fixes exactly which records it holds, and the count
                    and root cannot be revised afterwards without it being visible.
                  </p>
                  <SealActions records={records} seals={seals} onChange={world.reload} />
                </section>
              )}

              <section className="periods__section">
                <h2 className="periods__h2">
                  {verifier ? 'The seals behind that check' : 'Sealed'}
                </h2>
                {seals.length === 0 ? (
                  <Empty title="Nothing sealed" />
                ) : (
                  <div className="periods__grid">
                    {seals.map((s) => (
                      <PeriodSealCard key={s.bucket} seal={s} />
                    ))}
                  </div>
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
  held: string[];
  records: LedgerRecord[];
  grants: Grant[];
  orgs: Org[];
  onChange: () => void;
}) {
  const [, site, recordType, per] = bucket.split('|');
  const inPeriod = new Set(held);
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
  const undisclosed = held.filter((id) => !holdersOf.has(id));

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
  const [who, setWho] = useState(
    () => sibling?.requester_msp ?? counterparties[0]?.msp_id ?? '',
  );
  const [field, setField] = useState(() => sibling?.field_name ?? '');
  const [purpose, setPurpose] = useState(() => sibling?.purpose_code ?? '');
  const [until, setUntil] = useState(() => (sibling?.expires_at ?? '2028-12-31').slice(0, 10));
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const ready = who !== '' && field.trim() !== '' && purpose.trim() !== '' && until !== '';

  const disclose = async (recordId: string) => {
    setBusy(true);
    setFailure(null);
    try {
      await api.grant({
        record_id: recordId,
        requester_msp: who,
        purpose_code: purpose.trim(),
        field_name: field.trim(),
        expires_at: `${until}T00:00:00Z`,
      });
      setOpening(null);
      onChange();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'the grant was not written'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="whoholds">
      <div className="whoholds__records">
        <p className="stamp-type whoholds__label">What this period holds</p>
        <ul className="whoholds__ids">
          {held.map((id) => {
            const to = holdersOf.get(id) ?? [];
            return (
              <li key={id} className={`whoholds__id ${to.length ? '' : 'is-held'}`}>
                <span className="mono">{id}</span>
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
                      setOpening(opening === id ? null : id);
                    }}
                    aria-expanded={opening === id}
                  >
                    not disclosed
                  </button>
                )}
              </li>
            );
          })}
        </ul>

        {failure && <Failed error={failure} />}

        {opening && (
          <div className="whoholds__form">
            <p className="small">
              Release <span className="mono">{opening}</span> — one field, to one
              organisation, until a date you set.
            </p>

            <label className="whoholds__field">
              <span className="stamp-type">To</span>
              <select className="input" value={who} onChange={(e) => setWho(e.target.value)}>
                {counterparties.map((o) => (
                  <option key={o.msp_id} value={o.msp_id}>{o.name}</option>
                ))}
              </select>
            </label>

            <div className="whoholds__pair">
              <label className="whoholds__field">
                <span className="stamp-type">Field</span>
                <input
                  className="input mono"
                  value={field}
                  placeholder="cas_number"
                  onChange={(e) => setField(e.target.value)}
                />
              </label>
              <label className="whoholds__field">
                <span className="stamp-type">Purpose</span>
                <input
                  className="input mono"
                  value={purpose}
                  placeholder="REACH-COMPLIANCE"
                  onChange={(e) => setPurpose(e.target.value)}
                />
              </label>
            </div>

            <label className="whoholds__field">
              <span className="stamp-type">Until</span>
              <input
                className="input"
                type="date"
                value={until}
                onChange={(e) => setUntil(e.target.value)}
              />
            </label>

            <div className="whoholds__formrow">
              <button
                type="button"
                className="btn btn--primary btn--sm"
                disabled={busy || !ready}
                onClick={() => void disclose(opening)}
              >
                {busy ? 'Writing to the chain…' : 'Disclose this record'}
              </button>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => setOpening(null)}
              >
                Cancel
              </button>
            </div>

            <p className="small whoholds__note">
              {sibling
                ? 'Prefilled from the terms this kind of record was released on before. '
                : ''}
              This writes a grant, which is the only thing a disclosure ever is here.
              {seal ? (
                <>
                  {' '}The seal does not move — it fixed this period at{' '}
                  {commas(seal.record_count)} before any of it was released, and that is
                  what makes the buyer's check mean anything.
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
        )}

        <p className="small whoholds__note">
          Every record the ledger holds for this period, and who you released each one
          to. This list is yours alone — a buyer sees only what it was given, which is
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
              ? ' It is sealed and undisclosed, which is a complete answer — the seal '
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
          A buyer checking this period recomputes the root over what it was given and
          compares it to the count you fixed when you closed it.
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
    </div>
  );
}
