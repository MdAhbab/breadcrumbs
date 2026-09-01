import { Check, FileUp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { Field, HashChip, Seal } from '../components/ui';
import { BOLTS, RECORD_LABEL } from '../lib/data';
import { commas } from '../lib/format';
import { useReducedMotion } from '../lib/useMotionPref';
import './upload.css';

const STEPS = [
  { label: 'Normalise', note: 'Column names and types are checked against the schema.' },
  { label: 'Salt & hash each thread', note: 'Every row gets its own random salt, then a hash. Low-entropy rows cannot be guessed.' },
  { label: 'Weave the tree', note: 'Hashes combine in pairs, and again, until the file is one root.' },
  { label: 'Encrypt & store', note: 'The file itself is encrypted and stays on your own storage.' },
  { label: 'Seal to the ledger', note: 'Only the root, the type, the period and the site are committed.' },
];

/**
 * Sealing a record.
 *
 * The commit sequence is drawn rather than spinner-ed, because each step is a
 * thing the user should understand happened — particularly the two that explain
 * why this is safe: the per-row salt, and the fact that only a root leaves.
 *
 * "What leaves your building" is stated explicitly rather than implied. It is
 * reassurance, and it is also simply true.
 */
export default function Upload() {
  const reduced = useReducedMotion();
  const [file, setFile] = useState<string | null>(null);
  const [phase, setPhase] = useState<'idle' | 'weaving' | 'sealed'>('idle');
  const [step, setStep] = useState(-1);
  const timers = useRef<number[]>([]);

  useEffect(() => () => timers.current.forEach(window.clearTimeout), []);

  const seal = () => {
    setPhase('weaving');
    if (reduced) {
      setStep(STEPS.length);
      setPhase('sealed');
      return;
    }
    STEPS.forEach((_, i) => {
      timers.current.push(window.setTimeout(() => setStep(i), i * 700));
    });
    timers.current.push(
      window.setTimeout(() => { setStep(STEPS.length); setPhase('sealed'); }, STEPS.length * 700),
    );
  };

  if (phase === 'sealed') {
    return (
      <div className="up up--done">
        <Seal tone="sealed">Sealed</Seal>
        <h1 className="up__donehead">The record is on the ledger.</h1>
        <p className="lead up__donebody">
          1,912 threads were hashed and woven into a single root. The file itself did not
          move.
        </p>
        <div className="up__receipt">
          <div className="up__rrow">
            <span className="stamp-type">Commitment</span>
            <span className="mono">rc-006</span>
          </div>
          <div className="up__rrow">
            <span className="stamp-type">Root</span>
            <HashChip value={BOLTS[0].merkleRoot} />
          </div>
          <div className="up__rrow">
            <span className="stamp-type">Block</span>
            <span className="mono">#{commas(15103)}</span>
          </div>
        </div>
        <div className="up__doneactions">
          <Link to="/factory/records/rc-001" className="btn btn--primary btn--md">View the bolt</Link>
          <button
            type="button"
            className="btn btn--secondary btn--md"
            onClick={() => { setPhase('idle'); setStep(-1); setFile(null); }}
          >
            Seal another
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="up">
      <header className="up__head">
        <p className="stamp-type up__eyebrow">Apex Textile Ltd</p>
        <h1>Seal a record</h1>
        <p className="lead up__lede">
          A finalised export. Once sealed, its contents can be proved one thread at a time —
          and cannot be quietly changed.
        </p>
      </header>

      <div className="up__body">
        <div className="up__form">
          <div className="up__pair">
            <Field label="Record type" id="rtype">
              <select id="rtype" className="input" defaultValue="payroll_register">
                {Object.entries(RECORD_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </Field>
            <Field label="Period" id="per">
              <input id="per" className="input" type="month" defaultValue="2026-08" />
            </Field>
          </div>

          <Field label="Schema version" id="schema" hint="v2.1.0 is current for payroll registers.">
            <select id="schema" className="input">
              <option>v2.1.0</option>
              <option>v2.0.3</option>
            </select>
          </Field>

          <button
            type="button"
            className={`drop ${file ? 'has-file' : ''}`}
            onClick={() => setFile('apex-payroll-2026-08.csv')}
            disabled={phase === 'weaving'}
          >
            {file ? (
              <>
                <Check size={20} />
                <span className="drop__name mono">{file}</span>
                <span className="small drop__meta">1,912 rows · 214 KB · schema matched</span>
              </>
            ) : (
              <>
                <FileUp size={20} />
                <span className="drop__name">Drop a CSV or Excel export here</span>
                <span className="small drop__meta">or click to choose a file</span>
              </>
            )}
          </button>

          <button
            type="button"
            className="btn btn--primary btn--lg"
            disabled={!file || phase === 'weaving'}
            onClick={seal}
          >
            {phase === 'weaving' ? 'Weaving…' : 'Seal to the ledger'}
          </button>

          {phase === 'weaving' && (
            <ol className="weavesteps" aria-live="polite">
              {STEPS.map((s, i) => (
                <li key={s.label} className={i < step ? 'is-done' : i === step ? 'is-active' : ''}>
                  <span className="weavesteps__mark" aria-hidden="true" />
                  <span className="weavesteps__body">
                    <span className="weavesteps__label">{s.label}</span>
                    {i === step && <span className="small weavesteps__note">{s.note}</span>}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>

        {/* -- what leaves the building ---------------------------------- */}
        <aside className="leaves">
          <p className="stamp-type leaves__head">What leaves your building</p>
          <div className="leaves__col leaves__col--stay">
            <p className="leaves__title">Stays here</p>
            <ul>
              <li>The file itself, encrypted</li>
              <li>Every row and every value</li>
              <li>Worker references and names</li>
              <li>The salts, until a proof needs one</li>
            </ul>
            <p className="small leaves__note">Deletable. Nothing above is on the ledger.</p>
          </div>
          <div className="leaves__col leaves__col--go">
            <p className="leaves__title">Goes to the ledger</p>
            <ul>
              <li>One root hash</li>
              <li>Record type and period</li>
              <li>Site</li>
              <li>Row count and schema version</li>
            </ul>
            <p className="small leaves__note">Permanent. None of it identifies a person.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
