import { AbsenceProof } from '../components/AbsenceProof';
import { CompletenessChecker } from '../components/CompletenessChecker';
import { PeriodSealCard } from '../components/PeriodSealCard';
import { PageHead } from '../components/ui';
import { SEALS } from '../lib/anchor';
import { useSession } from '../lib/session';
import './periods.css';

/**
 * Closed periods, and the question they exist to answer.
 *
 * A factory reads this as bookkeeping: which periods it has closed, at what
 * count, and how often it has had to reopen one. A buyer reads it as the
 * completeness check, which is the reason the seal exists at all — so for a
 * buyer the checker comes first and the seals are the evidence behind it.
 */
export default function Periods() {
  const { role } = useSession();
  const verifier = role?.id === 'buyer' || role?.id === 'auditor';

  return (
    <div className="periods">
      <PageHead
        eyebrow={verifier ? 'Completeness' : 'Apex Textile Ltd · closed periods'}
        title={verifier ? 'Was anything withheld?' : 'Closed periods'}
        lede={
          verifier
            ? 'Other systems prove a record is genuine. A sealed period proves nothing is missing — the count and the root were fixed before you asked, so a short disclosure is arithmetic, not suspicion.'
            : 'Closing a period fixes exactly which records it holds. After that a late record cannot be slipped in quietly; it has to be an amendment, with a reason, in the open.'
        }
      />

      {verifier && (
        <section className="periods__section">
          <CompletenessChecker seal={SEALS[0]} />
        </section>
      )}

      <section className="periods__section">
        <h2 className="periods__h2">
          {verifier ? 'The seals behind that check' : 'Sealed'}
        </h2>
        <div className="periods__grid">
          {SEALS.map((s) => (
            <PeriodSealCard key={s.bucket} seal={s} />
          ))}
        </div>
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
    </div>
  );
}
