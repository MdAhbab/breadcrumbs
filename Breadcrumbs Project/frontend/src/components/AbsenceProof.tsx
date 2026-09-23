import { FileSearch, Search } from 'lucide-react';
import { useState } from 'react';

import { ApiError, api, type Absence } from '../lib/api';
import { Failed } from './states';
import { Tech } from './Tech';
import { Seal } from './ui';
import './mechanisms.css';

/**
 * Check that something was never filed.
 *
 * The easiest claim in the product to overstate, so the screen keeps two facts
 * apart: the ledger holds no document under this reference (a lookup), and it
 * was never added up to the latest update (a Bezout proof). Only the second is
 * cryptography, and its scope is narrow. The plain line says the limit in
 * words. The contract's own scope sentence is technical detail.
 */
export function AbsenceProof() {
  const [value, setValue] = useState('ISO45001-FORGED-Q3-2026');
  const [result, setResult] = useState<Absence | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    const key = value.trim();
    if (!key) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.nonMembership(key));
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err : new ApiError(0, 'the check could not be run'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="absence">
      <div className="absence__form">
        <label className="field__label" htmlFor="ref">
          Certificate or document reference
        </label>
        <div className="absence__row">
          <input
            id="ref"
            className="input mono"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void run()}
            placeholder="ISO45001-PASS-Q3-2026"
          />
          <button
            type="button"
            className="btn btn--primary btn--md"
            onClick={() => void run()}
            disabled={busy}
          >
            <Search size={14} /> {busy ? 'Checking…' : 'Check'}
          </button>
        </div>
        <p className="small field__hint">
          Type any reference. You will see if it was ever put on the ledger.
        </p>
      </div>

      {error && <Failed error={error} />}

      {result && (
        <div className={`absence__out ${result.never_committed ? 'is-absent' : 'is-present'}`}>
          <header className="absence__head">
            <FileSearch size={17} />
            <div>
              <p className="absence__verdict">
                {result.never_committed
                  ? 'This was never put on the ledger.'
                  : 'This is on the ledger.'}
              </p>
              <p className="small">
                {result.never_committed
                  ? `Checked, not just searched for.${
                    result.epoch === null ? '' : ` This holds up to update ${result.epoch}.`
                  } It says nothing about anything added later.`
                  : 'It is there, so there is nothing to check.'}
              </p>
            </div>
          </header>

          <div className="absence__rows">
            <div className="absence__r">
              <span className="stamp-type">Search the ledger</span>
              <Seal tone={result.ledger_holds_record ? 'sealed' : 'inert'}>
                {result.ledger_holds_record ? 'found' : 'not found'}
              </Seal>
            </div>
            <div className="absence__r">
              <span className="stamp-type">Tamper check</span>
              <Seal tone={result.proof_ok ? 'sealed' : 'broken'}>
                {result.provable
                  ? result.proof_ok ? 'never added' : 'failed'
                  : 'not needed'}
              </Seal>
            </div>
            <Tech>
              <div className="absence__r">
                <span className="stamp-type">Checked at</span>
                <span className="mono">
                  {result.epoch === null ? 'no epoch' : `epoch ${result.epoch}`}
                </span>
              </div>
            </Tech>
          </div>

          {result.reason && <p className="small absence__reason">{result.reason}</p>}
          <Tech><p className="small absence__scope">{result.scope}</p></Tech>
        </div>
      )}
    </div>
  );
}
