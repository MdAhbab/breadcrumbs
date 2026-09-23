import { ShieldCheck, ShieldOff, ShieldQuestion } from 'lucide-react';

import { CHECK_CODES, shortMsp, type WitnessRequirement } from '../lib/api';
import { dateTime } from '../lib/format';
import { ReviewedMark } from './ReviewSignoff';
import { Tech } from './Tech';
import { Seal } from './ui';
import './mechanisms.css';

/**
 * Who counter-signed this record, and what did they actually check?
 *
 * Three states, and conflating any two of them would misrepresent the ledger:
 *
 *   - the rule is not in force on this channel, so no counter-signature was
 *     ever required and its absence means nothing;
 *   - the rule is in force and this record was not in the sample, which is also
 *     not a fault;
 *   - the rule is in force, witnesses were assigned, and one of them did not
 *     sign — which is the only one of the three that is a problem.
 *
 * The check code matters as much as the signature. "Format only" and "physical
 * presence" are both attestations and they are not remotely the same evidence,
 * so the weight is drawn rather than left for the reader to infer.
 */
export function WitnessPanel({
  req, reviewCount = 0,
}: {
  req: WitnessRequirement;
  /** Confirmations of review standing against this document. A different
      signature entirely, shown here only so a reader stops looking. */
  reviewCount?: number;
}) {
  if (!req.in_force) {
    return (
      <section className="wit wit--off">
        <header className="wit__head">
          <ShieldOff size={16} />
          <div>
            <p className="wit__title">No counter-signature needed</p>
            <p className="small wit__sub">
              Counter-signing is not switched on here, so nothing is missing.
              <Tech> {req.reason}</Tech>
            </p>
          </div>
        </header>
        <AlsoReviewed n={reviewCount} />
      </section>
    );
  }

  if (req.predates_rule) {
    return (
      <section className="wit wit--none">
        <header className="wit__head">
          <ShieldQuestion size={16} />
          <div>
            <p className="wit__title">Filed before counter-signing started</p>
            <p className="small wit__sub">
              No counter-signature was needed, so nothing is missing.
              <Tech>
                {' '}Filed {dateTime(req.committed_at ?? '')}. Round {req.round_id} opened{' '}
                {dateTime(req.round_opened_at ?? '')}.
              </Tech>
            </p>
          </div>
        </header>
        <AlsoReviewed n={reviewCount} />
      </section>
    );
  }

  if (!req.required) {
    return (
      <section className="wit wit--none">
        <header className="wit__head">
          <ShieldQuestion size={16} />
          <div>
            <p className="wit__title">Not picked for counter-signing</p>
            <p className="small wit__sub">
              Only some documents are picked at random, so nothing is missing.
              <Tech> Round {req.round_id}.</Tech>
            </p>
          </div>
        </header>
        <AlsoReviewed n={reviewCount} />
      </section>
    );
  }

  const signed = new Set(req.attestations.map((a) => a.witness_msp));
  const outstanding = req.witnesses.filter((w) => !signed.has(w));

  return (
    <section className={`wit ${outstanding.length ? 'wit--short' : 'wit--ok'}`}>
      <header className="wit__head">
        <ShieldCheck size={16} />
        <div>
          <p className="wit__title">
            {outstanding.length
              ? `${req.attestations.length} of ${req.witnesses.length} picked organisations counter-signed`
              : `Counter-signed by ${req.witnesses.length} ${
                req.witnesses.length === 1 ? 'organisation' : 'organisations'}`}
          </p>
          <p className="small wit__sub">
            Picked at random from {req.pool_size}, not by the factory.
            <Tech> Round {req.round_id}.</Tech>
          </p>
        </div>
      </header>

      <ul className="wit__list">
        {req.witnesses.map((msp) => {
          const att = req.attestations.find((a) => a.witness_msp === msp);
          const code = att ? CHECK_CODES[att.check_code] : null;
          return (
            <li key={msp} className={`wit__row ${att ? '' : 'is-missing'}`}>
              <div className="wit__who">
                <span className="wit__msp">{shortMsp(msp)}</span>
                {att ? (
                  <span className="small wit__when">{dateTime(att.attested_at)}</span>
                ) : (
                  <span className="small wit__when">not signed</span>
                )}
              </div>

              {att && code ? (
                <div className="wit__claim">
                  <span className="wit__code">{code.label}</span>
                  <span className="wit__weight" aria-label={`how strong this evidence is: ${code.weight} of 4`}>
                    {[1, 2, 3, 4].map((n) => (
                      <span key={n} className={n <= code.weight ? 'is-on' : ''} />
                    ))}
                  </span>
                  <span className="small wit__note">{code.note}</span>
                </div>
              ) : (
                <Seal tone="broken">Did not sign</Seal>
              )}
            </li>
          );
        })}
      </ul>

      {outstanding.length > 0 && (
        <p className="small wit__warn">
          {outstanding.map(shortMsp).join(', ')} did not counter-sign. The document is
          still published, with less evidence behind it.
        </p>
      )}

      <AlsoReviewed n={reviewCount} />
    </section>
  );
}

/**
 * The other signature this product calls counter-signing, named on the panel
 * where the confusion actually lands.
 *
 * Somebody who has just signed a confirmation of review arrives at the heading
 * "Who counter-signed it when it was filed", finds their own name absent, and
 * concludes their signature did not take. It did: this panel is about the
 * witness the consortium assigned before the file was published, and a
 * confirmation of review is signed afterwards by whoever read the document.
 * Different party, different moment, different weight — so the count is set
 * apart from the attestations rather than added to them. Merging the two would
 * present an off-chain statement as an on-chain one, which is the one thing
 * this panel exists to keep straight.
 */
function AlsoReviewed({ n }: { n: number }) {
  if (n === 0) return null;
  return (
    <p className="small wit__also">
      <ReviewedMark n={n} /> signed later by readers. They are listed under the document.
    </p>
  );
}
