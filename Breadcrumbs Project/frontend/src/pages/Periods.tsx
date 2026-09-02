import { useState } from 'react';

import { AbsenceProof } from '../components/AbsenceProof';
import { CompletenessChecker } from '../components/CompletenessChecker';
import { PeriodSealCard } from '../components/PeriodSealCard';
import { SealActions } from '../components/SealActions';
import { Empty, Result } from '../components/states';
import { PageHead } from '../components/ui';
import { api, recordLabel, type LedgerRecord, type PeriodSeal } from '../lib/api';
import { period as periodName } from '../lib/format';
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
    () => Promise.all([api.seals(), api.records()]) as Promise<[PeriodSeal[], LedgerRecord[]]>,
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
        {([seals, records]) => {
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

                <CompletenessChecker
                  key={current.bucket}
                  seal={current}
                  sealedIds={inBucket(current.bucket)}
                  disclosedIds={inBucket(current.bucket)}
                />
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
