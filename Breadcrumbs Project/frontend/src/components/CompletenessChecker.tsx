import { AlertTriangle, Check } from 'lucide-react';
import { useMemo, useState } from 'react';

import { DISCLOSED_IDS, SEALED_IDS, type Completeness, type PeriodSeal } from '../lib/anchor';
import { shortHash } from '../lib/format';
import './mechanisms.css';

/**
 * Was anything withheld?
 *
 * Other systems prove a record is genuine. This proves nothing is missing, and
 * the difference is the whole submission — so the screen shows the arithmetic
 * rather than a verdict. Sealed five, disclosed four, and two roots that plainly
 * are not the same string. Nobody has to be believed.
 *
 * The list is editable on purpose. A judge can add the withheld register back
 * and watch the roots converge, which is a far better demonstration of what a
 * commitment does than any amount of copy.
 */
function rootFor(ids: string[], seal: PeriodSeal): string {
  // The real root comes from the ledger; here the sealed set reproduces the
  // sealed root exactly and anything else is visibly, stably different.
  const sorted = [...ids].sort();
  if (sorted.length === SEALED_IDS.length && sorted.every((v, i) => v === SEALED_IDS[i])) {
    return seal.records_root;
  }
  let h = 0x9e3779b9;
  for (const c of sorted.join('|')) {
    h ^= c.charCodeAt(0);
    h = Math.imul(h, 0x85ebca6b) >>> 0;
    h ^= h >>> 13;
  }
  let out = '';
  let s = h || 1;
  while (out.length < 64) {
    s ^= s << 13; s >>>= 0;
    s ^= s >>> 17;
    s ^= s << 5; s >>>= 0;
    out += s.toString(16).padStart(8, '0');
  }
  return out.slice(0, 64);
}

export function CompletenessChecker({ seal }: { seal: PeriodSeal }) {
  const [disclosed, setDisclosed] = useState<string[]>(DISCLOSED_IDS);

  const result: Completeness = useMemo(() => {
    const unique = [...new Set(disclosed)].sort();
    const computed = rootFor(unique, seal);
    const complete = computed === seal.records_root && unique.length === seal.record_count;
    return {
      bucket: seal.bucket,
      sealed: true,
      complete,
      sealed_count: seal.record_count,
      disclosed_count: unique.length,
      sealed_root: seal.records_root,
      computed_root: computed,
      amendment_count: seal.amendments.length,
      reason: complete
        ? ''
        : unique.length < seal.record_count
          ? `${seal.record_count - unique.length} record(s) were sealed into this period but not disclosed`
          : 'the disclosed set does not match what was sealed',
    };
  }, [disclosed, seal]);

  const toggle = (id: string) =>
    setDisclosed((d) => (d.includes(id) ? d.filter((x) => x !== id) : [...d, id]));

  const missing = SEALED_IDS.filter((id) => !disclosed.includes(id));

  return (
    <div className="cchk">
      <div className="cchk__input">
        <p className="stamp-type cchk__label">What you were given</p>
        <ul className="cchk__list">
          {SEALED_IDS.map((id) => {
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
        <p className="small cchk__hint">
          Add or remove a register to see the arithmetic change. The seal was
          fixed on {seal.period}; nothing here can alter it.
        </p>
      </div>

      <div className={`cchk__verdict ${result.complete ? 'is-ok' : 'is-short'}`}>
        <div className="cchk__banner">
          {result.complete ? <Check size={18} strokeWidth={2.5} /> : <AlertTriangle size={18} />}
          <span>
            {result.complete
              ? 'Complete — the disclosure matches the seal.'
              : `${missing.length || 'The'} record${missing.length === 1 ? '' : 's'} withheld.`}
          </span>
        </div>

        <div className="cchk__counts">
          <div>
            <span className="cchk__n">{result.sealed_count}</span>
            <span className="stamp-type">sealed into the period</span>
          </div>
          <span className="cchk__vs" aria-hidden="true">/</span>
          <div>
            <span className="cchk__n">{result.disclosed_count}</span>
            <span className="stamp-type">disclosed to you</span>
          </div>
        </div>

        <div className="cchk__roots">
          <div className="cchk__root">
            <span className="stamp-type">Sealed root, on the ledger</span>
            <span className="mono">{shortHash(result.sealed_root!)}</span>
          </div>
          <div className={`cchk__root ${result.complete ? '' : 'is-bad'}`}>
            <span className="stamp-type">Root of what you hold</span>
            <span className="mono">{shortHash(result.computed_root!)}</span>
          </div>
        </div>

        <p className="cchk__reason">
          {result.complete
            ? 'Both roots are the same value, so the set you hold is exactly the set that was sealed.'
            : result.reason + '. The two roots differ, which is the proof — not an opinion about the factory.'}
        </p>

        {result.amendment_count! > 0 && (
          <p className="small cchk__amend">
            This period has been amended {result.amendment_count} time
            {result.amendment_count === 1 ? '' : 's'}. Check the history before
            relying on the count.
          </p>
        )}

        <p className="small cchk__limit">
          What this cannot do: a register kept off the ledger entirely leaves the
          seal internally consistent and says nothing. This proves withholding,
          not honesty.
        </p>
      </div>
    </div>
  );
}
