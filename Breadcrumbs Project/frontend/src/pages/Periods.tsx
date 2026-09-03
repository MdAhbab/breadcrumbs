import { useState } from 'react';

import { AbsenceProof } from '../components/AbsenceProof';
import { CompletenessChecker } from '../components/CompletenessChecker';
import { PeriodSealCard } from '../components/PeriodSealCard';
import { SealActions } from '../components/SealActions';
import { Empty, Result } from '../components/states';
import { PageHead } from '../components/ui';
import {
  api, recordLabel, shortMsp,
  type Grant, type LedgerRecord, type PeriodSeal,
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
  seal, held, grants,
}: {
  seal: PeriodSeal;
  held: string[];
  grants: Grant[];
}) {
  const inPeriod = new Set(held);
  const live = new Map<string, number>();
  const ended = new Map<string, number>();
  for (const g of grants) {
    if (!inPeriod.has(g.record_id)) continue;
    const tally = g.status === 'active' ? live : ended;
    tally.set(g.requester_msp, (tally.get(g.requester_msp) ?? 0) + 1);
  }
  const holders = [...new Set([...live.keys(), ...ended.keys()])].sort();

  return (
    <div className="whoholds">
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
          and undisclosed, which is a complete answer — the seal exists so that a
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
      </p>
    </div>
  );
}
