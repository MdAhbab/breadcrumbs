import { ShieldCheck, ShieldOff, ShieldQuestion } from 'lucide-react';

import { CHECK_CODES, type WitnessRequirement } from '../lib/anchor';
import { dateTime } from '../lib/format';
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
export function WitnessPanel({ req }: { req: WitnessRequirement }) {
  if (!req.in_force) {
    return (
      <section className="wit wit--off">
        <header className="wit__head">
          <ShieldOff size={16} />
          <div>
            <p className="wit__title">The witness rule is not in force</p>
            <p className="small wit__sub">
              {req.reason
                ?? 'the consortium has not adopted the witness rule on this channel'}
              . No counter-signature was required for this record, so its absence
              is not a finding.
            </p>
          </div>
        </header>
      </section>
    );
  }

  if (!req.required) {
    return (
      <section className="wit wit--none">
        <header className="wit__head">
          <ShieldQuestion size={16} />
          <div>
            <p className="wit__title">Not selected for counter-signature</p>
            <p className="small wit__sub">
              The rule is in force under round {req.round_id}, and the sample did
              not draw this record. Nothing is missing.
            </p>
          </div>
        </header>
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
              ? `${req.attestations.length} of ${req.witnesses.length} assigned witnesses signed`
              : `Counter-signed by ${req.witnesses.length} assigned witnesses`}
          </p>
          <p className="small wit__sub">
            Assigned by round {req.round_id} from a pool of {req.pool_size}. The
            factory did not choose them, and could not: the seed came from a
            commit–reveal round no member controls.
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
                <span className="wit__msp mono">{msp}</span>
                {att ? (
                  <span className="small wit__when">{dateTime(att.attested_at)}</span>
                ) : (
                  <span className="small wit__when">no attestation on the ledger</span>
                )}
              </div>

              {att && code ? (
                <div className="wit__claim">
                  <span className="wit__code">{code.label}</span>
                  <span className="wit__weight" aria-label={`evidentiary weight ${code.weight} of 4`}>
                    {[1, 2, 3, 4].map((n) => (
                      <span key={n} className={n <= code.weight ? 'is-on' : ''} />
                    ))}
                  </span>
                  <span className="small wit__note">{code.note}</span>
                </div>
              ) : (
                <Seal tone="broken">did not sign</Seal>
              )}
            </li>
          );
        })}
      </ul>

      {outstanding.length > 0 && (
        <p className="small wit__warn">
          {outstanding.join(', ')} was assigned and did not attest. The record is
          still committed — the ledger does not refuse it — but it carries less
          evidence than the rule asks for.
        </p>
      )}
    </section>
  );
}
