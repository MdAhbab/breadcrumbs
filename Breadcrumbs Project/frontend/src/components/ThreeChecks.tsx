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
 * separate. The forgeable one is labelled once, in technical detail only.
 */

/**
 * Plain wording for each check, in the product's own words. The API's plain
 * labels say "record" and "the single number", which this screen does not use.
 */
const PLAIN_LABEL: Record<string, string> = {
  ledger: 'The ledger has this document, and it matches',
  witness: 'The tamper check covers it',
  index: 'It was added on a known date, in the open',
};
const PLAIN_OK_DETAIL: Record<string, string> = {
  witness: 'The tamper check for the whole ledger includes this document.',
};
export function ThreeChecks({ result }: { result: Verification }) {
  const { technical } = useDetail();

  if (!result.anchored) {
    return (
      <section className="tcheck tcheck--off">
        <p className="tcheck__title">Nothing to check this against yet</p>
        <p className="small">
          {result.reason || 'The tamper check is not set up here yet.'}
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
              <p className="tcheck__label">
                {technical ? c.label : PLAIN_LABEL[c.id] ?? c.plain_label}
              </p>
              <p className="small tcheck__detail">
                {technical ? c.detail : (c.ok && PLAIN_OK_DETAIL[c.id]) || c.plain_detail}
              </p>
              {technical && c.forgeable_by_trapdoor && (
                <p className="small tcheck__forge">
                  <AlertTriangle size={12} /> {result.note}
                </p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
