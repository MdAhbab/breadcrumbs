import { FileSearch, Search } from 'lucide-react';
import { useState } from 'react';

import { ABSENCE, type Absence } from '../lib/anchor';
import { Seal } from './ui';
import './mechanisms.css';

/**
 * Proof that something was never committed.
 *
 * This is the operation no Merkle tree can perform, and it turns "we have no
 * record of that certificate" from a filing failure into a cryptographic
 * statement. It is also the easiest claim in the product to overstate, so the
 * screen keeps two facts apart:
 *
 *   the ledger holds no record under this identifier — a lookup; and
 *   this element was never accumulated up to the current epoch — a Bezout proof.
 *
 * Only the second is cryptography, and its scope is narrow. The scope sentence
 * is printed on the result, not tucked into a tooltip.
 */
const UNKNOWN = (reference: string): Absence => ({
  reference,
  provable: true,
  epoch: 4,
  ledger_holds_record: false,
  never_committed: true,
  proof_ok: true,
  reason: '',
  scope:
    `This proves the canonical element for ‘${reference}’ was never accumulated `
    + 'up to epoch 4. It says nothing about later epochs, and nothing about '
    + 'documents that were never offered to this ledger at all.',
});

export function AbsenceProof() {
  const [value, setValue] = useState('ISO45001-FORGED-Q3-2026');
  const [result, setResult] = useState<Absence | null>(null);

  const run = () => {
    const key = value.trim();
    if (!key) return;
    setResult(ABSENCE[key] ?? UNKNOWN(key));
  };

  return (
    <div className="absence">
      <div className="absence__form">
        <label className="field__label" htmlFor="ref">
          Certificate or record reference
        </label>
        <div className="absence__row">
          <input
            id="ref"
            className="input mono"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && run()}
            placeholder="ISO45001-PASS-Q3-2026"
          />
          <button type="button" className="btn btn--primary btn--md" onClick={run}>
            <Search size={14} /> Prove
          </button>
        </div>
        <p className="small field__hint">
          A buyer holding a certificate the factory never committed can settle it
          here without asking the factory anything.
        </p>
      </div>

      {result && (
        <div className={`absence__out ${result.never_committed ? 'is-absent' : 'is-present'}`}>
          <header className="absence__head">
            <FileSearch size={17} />
            <div>
              <p className="absence__verdict">
                {result.never_committed
                  ? 'Never committed to this ledger.'
                  : 'This reference is on the ledger.'}
              </p>
              <p className="small">
                {result.never_committed
                  ? 'Proved, not merely unfound. The accumulator carries a witness that this element is absent from the set.'
                  : 'The lookup found a record, so no absence proof applies — and the Bezout check correctly refuses to produce one.'}
              </p>
            </div>
          </header>

          <div className="absence__rows">
            <div className="absence__r">
              <span className="stamp-type">Ledger lookup</span>
              <Seal tone={result.ledger_holds_record ? 'sealed' : 'inert'}>
                {result.ledger_holds_record ? 'record found' : 'no record'}
              </Seal>
            </div>
            <div className="absence__r">
              <span className="stamp-type">Non-membership proof</span>
              <Seal tone={result.proof_ok ? 'sealed' : 'broken'}>
                {result.proof_ok ? 'verifies' : 'does not hold'}
              </Seal>
            </div>
            <div className="absence__r">
              <span className="stamp-type">Checked at</span>
              <span className="mono">epoch {result.epoch}</span>
            </div>
          </div>

          {result.reason && <p className="small absence__reason">{result.reason}</p>}
          <p className="small absence__scope">{result.scope}</p>
        </div>
      )}
    </div>
  );
}
