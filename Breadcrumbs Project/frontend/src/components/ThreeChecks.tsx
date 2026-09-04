import { AlertTriangle, Check, X } from 'lucide-react';

import type { Verification } from '../lib/api';
import { useDetail } from '../lib/detail';
import './mechanisms.css';

/**
 * Three checks, three rows. This is the one component that must not be tidied.
 *
 * `model/anchoring.py:verify_record` runs three independent checks, and the
 * temptation is to render their conjunction as a single green tick. Doing that
 * would throw away the entire defence: the RSA modulus came from a
 * trusted-dealer ceremony, so a holder of its factorisation can forge check 2 —
 * there is a passing test in the model that does exactly that — and checks 1
 * and 3 are the only reason the forgery fails anyway.
 *
 * A combined badge would show that forged record as verified. So the rows stay
 * separate, the forgeable one is labelled as forgeable, and the explainer says
 * why in the fewest words that are still true.
 */
export function ThreeChecks({ result }: { result: Verification }) {
  const { technical } = useDetail();

  if (!result.anchored) {
    return (
      <section className="tcheck tcheck--off">
        <p className="tcheck__title">Nothing to check this against yet</p>
        <p className="small">
          {result.reason || 'The tamper check has not been set up on this part of the network, so there is nothing to compare against.'}
        </p>
      </section>
    );
  }

  return (
    <section className={`tcheck ${result.verified ? 'is-ok' : 'is-bad'}`}>
      <header className="tcheck__head">
        <span className="tcheck__mark" aria-hidden="true">
          {result.verified ? <Check size={17} strokeWidth={2.5} /> : <X size={17} strokeWidth={2.5} />}
        </span>
        <div>
          <p className="tcheck__title">
            {result.verified
              ? 'All three checks pass. This has not been altered.'
              : `${result.checks.filter((c) => !c.ok).length} of 3 checks failed`}
          </p>
          <p className="small tcheck__sub">
            Three separate checks, run independently. The verdict is simply all three
            agreeing. There is no fourth opinion on top of them.
          </p>
        </div>
      </header>

      <ol className="tcheck__list">
        {result.checks.map((c, i) => (
          <li key={c.id} className={`tcheck__row ${c.ok ? 'is-ok' : 'is-bad'}`}>
            <span className="mono tcheck__n">{i + 1}</span>
            <span className="tcheck__state" aria-hidden="true">
              {c.ok ? <Check size={13} strokeWidth={3} /> : <X size={13} strokeWidth={3} />}
            </span>
            <div className="tcheck__body">
              <p className="tcheck__label">{technical ? c.label : c.plain_label}</p>
              <p className="small tcheck__detail">
                {technical ? c.detail : c.plain_detail}
              </p>
              {c.forgeable_by_trapdoor && (
                <p className="small tcheck__forge">
                  <AlertTriangle size={12} />{' '}
                  {technical
                    ? 'This is the check a holder of the modulus factorisation could forge.'
                    : 'This is the one check somebody with the original setup secret could fake. The other two would still catch them.'}
                </p>
              )}
            </div>
          </li>
        ))}
      </ol>

      <p className="small tcheck__why">
        {technical ? result.note : result.plain_note}
      </p>
    </section>
  );
}
