import { useState } from 'react';

import { AbsenceProof } from '../components/AbsenceProof';
import { CompletenessChecker } from '../components/CompletenessChecker';
import { PeriodSealCard } from '../components/PeriodSealCard';
import { SealActions } from '../components/SealActions';
import { Empty, Failed, Result } from '../components/states';
import { PageHead } from '../components/ui';
import {
  ApiError, api, recordLabel, shortMsp,
  type Grant, type LedgerRecord, type PeriodSeal,
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
    () => Promise.all([api.seals(), api.records(), api.grants()]) as
      Promise<[PeriodSeal[], LedgerRecord[], Grant[]]>,
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
        isEmpty={([seals]) => seals.length === 0}
        empty={{
          title: 'No sealed periods you can see',
          detail: verifier
            ? 'A period becomes visible to you once you hold a live grant against a record inside it.'
            : 'Nothing has been sealed yet. Sealing a period fixes which records it holds.',
        }}
      >
        {([seals, records, grants]) => {
          const inBucket = (bucket: string) =>
            records.filter((r) => r.bucket === bucket).map((r) => r.record_id).sort();

          // Default to a period whose disclosure is short — the case worth
          // looking at. If none is, the first seal will do.
          const short = seals.find((s) => inBucket(s.bucket).length < s.record_count);
          const current = seals.find((s) => s.bucket === picked)
            ?? short
            ?? seals[0];

          return (
            <>
              <section className="periods__section">
                <div className="periods__picker">
                  <label className="periods__pick">
                    <span className="stamp-type">Period to check</span>
                    <select
                      className="input"
                      value={current.bucket}
                      onChange={(e) => setPicked(e.target.value)}
                    >
                      {seals.map((s) => {
                        const held = inBucket(s.bucket).length;
                        return (
                          <option key={s.bucket} value={s.bucket}>
                            {s.site} · {recordLabel(s.record_type)} · {periodName(s.period)}
                            {held < s.record_count ? ` — short by ${s.record_count - held}` : ''}
                          </option>
                        );
                      })}
                    </select>
                  </label>
                  {short && (
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
                {verifier ? (
                  <CompletenessChecker
                    key={current.bucket}
                    seal={current}
                    sealedIds={inBucket(current.bucket)}
                    disclosedIds={inBucket(current.bucket)}
                  />
                ) : (
                  <WhoHolds
                    seal={current}
                    held={inBucket(current.bucket)}
                    grants={grants}
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
function WhoHolds({
  seal, held, grants, onChange,
}: {
  seal: PeriodSeal;
  held: string[];
  grants: Grant[];
  onChange: () => void;
}) {
  const [opening, setOpening] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const inPeriod = new Set(held);

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

  // The terms the rest of this period was released on. A record left out of a
  // disclosure is nearly always an omission rather than a decision, so the
  // form offers to put it on the same footing as its forty neighbours instead
  // of asking a factory to reconstruct a purpose code from memory.
  const sibling = grants.find((g) => inPeriod.has(g.record_id) && g.status === 'active');

  const disclose = async (recordId: string) => {
    if (!sibling) return;
    setBusy(true);
    setFailure(null);
    try {
      await api.grant({
        record_id: recordId,
        requester_msp: sibling.requester_msp,
        purpose_code: sibling.purpose_code,
        field_name: sibling.field_name,
        expires_at: sibling.expires_at,
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
                ) : sibling ? (
                  <button
                    type="button"
                    className="whoholds__disclose small"
                    onClick={() => setOpening(opening === id ? null : id)}
                    aria-expanded={opening === id}
                  >
                    not disclosed
                  </button>
                ) : (
                  <span className="small whoholds__to">not disclosed</span>
                )}
              </li>
            );
          })}
        </ul>
        {failure && <Failed error={failure} />}

        {opening && sibling && (
          <div className="whoholds__form">
            <p className="small">
              Release <span className="mono">{opening}</span> to{' '}
              {shortMsp(sibling.requester_msp)} on the same terms as the rest of this
              period — <span className="mono">{sibling.field_name}</span>,{' '}
              <span className="mono">{sibling.purpose_code}</span>, until{' '}
              {longDate(sibling.expires_at)}.
            </p>
            <div className="whoholds__formrow">
              <button
                type="button"
                className="btn btn--primary btn--sm"
                disabled={busy}
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
              This writes a grant, which is the only thing a disclosure ever is here.
              The seal does not move — it fixed this period at {commas(seal.record_count)}{' '}
              before any of it was released, and that is what makes the buyer's check
              mean anything.
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
          <span className="whoholds__n">{commas(seal.record_count)}</span>
          <span className="small">
            sealed into {recordLabel(seal.record_type)}, {periodName(seal.period)} ·{' '}
            {seal.site} · version {seal.version}
          </span>
        </p>

        {holders.length === 0 ? (
          <p className="small whoholds__note">
            No counterparty holds a grant against anything in this period. It is sealed
            and undisclosed, which is a complete answer — the seal exists so a
            disclosure can be checked against it later, not because one has to be made.
          </p>
        ) : (
          <ul className="whoholds__list">
            {holders.map((msp) => {
              const n = live.get(msp) ?? 0;
              const short = seal.record_count - n;
              const revoked = ended.get(msp) ?? 0;
              return (
                <li key={msp} className={`whoholds__row ${short > 0 ? 'is-short' : ''}`}>
                  <span className="whoholds__who">{shortMsp(msp)}</span>
                  <span className="mono whoholds__of">
                    {commas(n)} of {commas(seal.record_count)}
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
          compares it to the count above, which you fixed before you disclosed anything.
          Where it is short, the two roots differ and the shortfall is arithmetic rather
          than an accusation. That is the same fact as this screen, seen from the other
          end.
          {undisclosed.length > 0 && (
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
