import { AlertTriangle, Check, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { ApiError, api, type Completeness, type PeriodSeal } from '../lib/api';
import { shortHash } from '../lib/format';
import { Failed } from './states';
import { Tech } from './Tech';
import './mechanisms.css';

/**
 * Was anything withheld?
 *
 * Other systems prove a record is genuine. This proves nothing is missing, and
 * the difference is the whole submission — so the screen shows the arithmetic
 * rather than a verdict. Sealed twenty-four, disclosed twenty-three, and two
 * roots that plainly are not the same string. Nobody has to be believed.
 *
 * Both roots come from the contract. An earlier version of this component
 * computed the "root of what you hold" in the browser with an xorshift, which
 * meant the most load-bearing screen in the product was showing a number it had
 * made up: it would have reported a mismatch for a disclosure that was in fact
 * complete, and nothing on the page would have said so.
 *
 * The list stays editable on purpose. Adding the withheld register back and
 * watching the roots converge — with the answer coming from the ledger each
 * time — is a better demonstration of what a commitment does than any copy.
 */
export function CompletenessChecker({
  seal,
  sealedIds,
  disclosedIds,
}: {
  seal: PeriodSeal;
  /** Every record the period holds, as far as this caller can see. */
  sealedIds: string[];
  /** What this caller was actually given. */
  disclosedIds: string[];
}) {
  const [disclosed, setDisclosed] = useState<string[]>(disclosedIds);
  const [result, setResult] = useState<Completeness | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => setDisclosed(disclosedIds), [disclosedIds]);

  useEffect(() => {
    let live = true;
    setBusy(true);
    setError(null);
    api
      .completeness({
        owner_msp: seal.owner_msp,
        site: seal.site,
        record_type: seal.record_type,
        period: seal.period,
        disclosed_record_ids: [...new Set(disclosed)],
      })
      .then((r) => live && setResult(r))
      .catch((err: unknown) => {
        if (!live) return;
        setResult(null);
        setError(err instanceof ApiError ? err : new ApiError(0, 'the check failed'));
      })
      .finally(() => live && setBusy(false));
    return () => {
      live = false;
    };
  }, [disclosed, seal]);

  const toggle = (id: string) =>
    setDisclosed((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));

  // How many are missing is the ledger's arithmetic, not a count of what this
  // caller can see. A buyer holds only what it was given, so the withheld ids
  // are not in `sealedIds` and never can be — that asymmetry is the mechanism.
  // Counting locally produced "A records withheld" when the shortfall was 1.
  const shortfall = Math.max(
    0,
    (result?.sealed_count ?? 0) - (result?.disclosed_count ?? 0),
  );

  return (
    <div className="cchk">
      <div className="cchk__input">
        <p className="stamp-type cchk__label">What you were given</p>
        {sealedIds.length === 0 ? (
          <p className="small cchk__hint">
            You hold no records in this period, so there is nothing to check against
            its seal.
          </p>
        ) : (
          <ul className="cchk__list">
            {sealedIds.map((id) => {
              const on = disclosed.includes(id);
              return (
                <li key={id}>
                  <button
                    type="button"
                    className={`cchk__item ${on ? 'is-on' : ''}`}
                    onClick={() => toggle(id)}
                    aria-pressed={on}
                  >
                    <span className="cchk__box" aria-hidden="true">
                      {on && <Check size={12} strokeWidth={3} />}
                    </span>
                    <span className="mono">{id}</span>
                    {!on && <span className="small cchk__held">not disclosed</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        <p className="small cchk__hint">
          Add or remove a register and the ledger recomputes the root. The seal was
          fixed when the period closed; nothing here can alter it.
        </p>
      </div>

      {error ? (
        <Failed error={error} />
      ) : result === null ? (
        <div className="cchk__verdict">
          <div className="cchk__banner"><Loader2 size={18} /> <span>Asking the ledger…</span></div>
        </div>
      ) : !result.sealed ? (
        <div className="cchk__verdict is-short">
          <div className="cchk__banner">
            <AlertTriangle size={18} />
            <span>
              {result.status === 'reopened'
                ? 'This month was reopened and has not been closed again.'
                : 'This month has never been closed.'}
            </span>
          </div>
          <p className="cchk__reason">{result.reason}</p>
        </div>
      ) : (
        <div className={`cchk__verdict ${result.complete ? 'is-ok' : 'is-short'}`}>
          <div className="cchk__banner">
            {result.complete ? <Check size={18} strokeWidth={2.5} /> : <AlertTriangle size={18} />}
            <span>
              {result.complete
                ? 'Nothing is missing. You were shown everything this month holds.'
                : shortfall > 0
                  ? `${shortfall} record${shortfall === 1 ? '' : 's'} held back from you.`
                  : 'What you were shown does not match what this month holds.'}
            </span>
            {busy && <span className="small dim">rechecking…</span>}
          </div>

          <div className="cchk__counts">
            <div>
              <span className="cchk__n">{result.sealed_count}</span>
              <span className="stamp-type">in the closed month</span>
            </div>
            <span className="cchk__vs" aria-hidden="true">/</span>
            <div>
              <span className="cchk__n">{result.disclosed_count}</span>
              <span className="stamp-type">shown to you</span>
            </div>
          </div>

          <Tech>
            <div className="cchk__roots">
              <div className="cchk__root">
                <span className="stamp-type">Sealed root, on the ledger</span>
                <span className="mono">{shortHash(result.sealed_root ?? '')}</span>
              </div>
              <div className={`cchk__root ${result.complete ? '' : 'is-bad'}`}>
                <span className="stamp-type">Root of what you hold</span>
                <span className="mono">{shortHash(result.computed_root ?? '')}</span>
              </div>
            </div>
          </Tech>

          <p className="cchk__reason">
            {result.complete
              ? 'The month was closed at this exact list of records before you asked, and what you hold is that list. Nothing was left out.'
              : `${result.reason}. The month says it holds more than you were shown. That is arithmetic, not an accusation.`}
          </p>

          {(result.amendment_count ?? 0) > 0 && (
            <p className="small cchk__amend">
              This month has been corrected {result.amendment_count} time
              {result.amendment_count === 1 ? '' : 's'}. Read the corrections before
              relying on the count.
            </p>
          )}

          <p className="small cchk__limit">
            What this cannot do: a file the factory never put on the ledger at all
            leaves everything here looking consistent. This catches things being held
            back from you. It does not prove the factory is honest.
          </p>
        </div>
      )}
    </div>
  );
}
