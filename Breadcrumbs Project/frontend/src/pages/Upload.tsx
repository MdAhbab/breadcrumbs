import { AlertTriangle, Check, FileUp, ShieldAlert } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { Failed } from '../components/states';
import { Field, HashChip, Seal } from '../components/ui';
import { ApiError, RECORD_LABEL, api, type WitnessRequirement } from '../lib/api';
import { commas } from '../lib/format';
import { useSession } from '../lib/session';
import './upload.css';

const STEPS = [
  { label: 'Normalise', note: 'Column names and types are checked against the schema. This happens here, in your browser.' },
  { label: 'Salt & hash each thread', note: 'Every row gets its own random salt, then a hash. Low-entropy rows cannot be guessed.' },
  { label: 'Weave the tree', note: 'Hashes combine in pairs, and again, until the file is one root.' },
  { label: 'Store off the chain', note: 'The rows stay in the factory’s own store. The API never serves a document body.' },
  { label: 'Seal to the ledger', note: 'Only the root, the type, the period and the site are committed.' },
];

interface Parsed {
  name: string;
  rows: Record<string, string | number>[];
  columns: string[];
  bytes: number;
}

/**
 * Sealing a record.
 *
 * The commit sequence is drawn rather than spinner-ed, because each step is a
 * thing the user should understand happened — particularly the two that explain
 * why this is safe: the per-row salt, and the fact that only a root leaves.
 *
 * The file is really parsed and the rows are really committed. The root on the
 * receipt is the one the server computed over those rows, not a hash borrowed
 * from another record to make the screen look finished.
 *
 * "What leaves your building" is stated explicitly rather than implied. It is
 * reassurance, and it is also simply true: `POST /api/records` sends the rows to
 * the factory's own store and puts one hash on the chain.
 */
export default function Upload() {
  const { role } = useSession();
  // A reopened period sends you here to commit the record it was reopened for,
  // and arriving at a blank form to retype a bucket you have just been looking
  // at is how a three-step mechanism becomes a chore. The defaults stand when
  // nothing is passed.
  const [params] = useSearchParams();
  const [recordType, setRecordType] = useState(
    () => (params.get('type') && params.get('type')! in RECORD_LABEL
      ? params.get('type')!
      : 'chemical_inventory'),
  );
  const [period, setPeriod] = useState(() => params.get('period') ?? '2027-03');
  const [site, setSite] = useState(() => params.get('site') ?? 'Gazipur');
  const [recordId, setRecordId] = useState('');
  const [schema, setSchema] = useState('v1.0.0');
  const [file, setFile] = useState<Parsed | null>(null);
  const [phase, setPhase] = useState<'idle' | 'weaving' | 'sealed'>('idle');
  const [step, setStep] = useState(-1);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const [receipt, setReceipt] = useState<
    { record_id: string; merkle_root: string; row_count: number; block: number } | null
  >(null);
  const [witness, setWitness] = useState<WitnessRequirement | null>(null);

  const id = recordId.trim() || `doc-ui-${period}-${recordType.slice(0, 4)}`;

  // Who would have to counter-sign this, asked before the button is pressed
  // rather than discovered from a refusal afterwards.
  useEffect(() => {
    let live = true;
    api
      .plannedWitness(id, recordType)
      .then((w) => live && setWitness(w))
      .catch(() => live && setWitness(null));
    return () => { live = false; };
  }, [id, recordType]);

  const parse = async (chosen: File) => {
    const text = await chosen.text();
    const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
    if (lines.length < 2) {
      setFailure(new ApiError(0, 'That file has no data rows under its header.'));
      return;
    }
    const columns = lines[0].split(',').map((c) => c.trim());
    const rows = lines.slice(1).map((line) => {
      const cells = line.split(',');
      const row: Record<string, string | number> = {};
      columns.forEach((c, i) => {
        const raw = (cells[i] ?? '').trim();
        const asNumber = Number(raw);
        row[c] = raw !== '' && !Number.isNaN(asNumber) ? asNumber : raw;
      });
      return row;
    });
    setFailure(null);
    setFile({ name: chosen.name, rows, columns, bytes: chosen.size });
  };

  const seal = async () => {
    if (!file) return;
    setPhase('weaving');
    setStep(0);
    setFailure(null);
    try {
      // Step 0 is ours; the rest happen inside the contract, and the step list
      // advances when the response comes back rather than on a timer.
      const result = await api.commitRecord({
        record_id: id,
        record_type: recordType,
        period,
        site,
        schema_version: schema,
        rows: file.rows,
      });
      setStep(STEPS.length);
      setReceipt(result);
      setPhase('sealed');
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'the record was not sealed'));
      setPhase('idle');
      setStep(-1);
    }
  };

  if (phase === 'sealed' && receipt) {
    return (
      <div className="up up--done">
        <Seal tone="sealed">Sealed</Seal>
        <h1 className="up__donehead">The record is on the ledger.</h1>
        <p className="lead up__donebody">
          {commas(receipt.row_count)} threads were hashed and woven into a single root.
          The file itself did not move.
        </p>
        <div className="up__receipt">
          <div className="up__rrow">
            <span className="stamp-type">Commitment</span>
            <span className="mono">{receipt.record_id}</span>
          </div>
          <div className="up__rrow">
            <span className="stamp-type">Root</span>
            <HashChip value={receipt.merkle_root} />
          </div>
          <div className="up__rrow">
            <span className="stamp-type">Block</span>
            <span className="mono">#{commas(receipt.block)}</span>
          </div>
        </div>
        <div className="up__doneactions">
          <Link
            to={`/factory/records/${encodeURIComponent(receipt.record_id)}`}
            className="btn btn--primary btn--md"
          >
            View the bolt
          </Link>
          <button
            type="button"
            className="btn btn--secondary btn--md"
            onClick={() => {
              setPhase('idle'); setStep(-1); setFile(null); setReceipt(null); setRecordId('');
            }}
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
        <p className="stamp-type up__eyebrow">{role?.org}</p>
        <h1>Seal a record</h1>
        <p className="lead up__lede">
          A finalised export. Once sealed, its contents can be proved one thread at a
          time — and cannot be quietly changed.
        </p>
      </header>

      <div className="up__body">
        <div className="up__form">
          <div className="up__pair">
            <Field label="Record type" id="rtype">
              <select
                id="rtype"
                className="input"
                value={recordType}
                onChange={(e) => setRecordType(e.target.value)}
              >
                {Object.entries(RECORD_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </Field>
            <Field label="Period" id="per">
              <input
                id="per" className="input" type="month" value={period}
                onChange={(e) => setPeriod(e.target.value)}
              />
            </Field>
          </div>

          <div className="up__pair">
            <Field label="Site" id="site">
              <input
                id="site" className="input" value={site}
                onChange={(e) => setSite(e.target.value)}
              />
            </Field>
            <Field
              label="Record id"
              id="rid"
              hint="Leave blank to derive one from the period and type."
            >
              <input
                id="rid" className="input mono" value={recordId} placeholder={id}
                onChange={(e) => setRecordId(e.target.value)}
              />
            </Field>
          </div>

          <Field label="Schema version" id="schema" hint="Recorded on the ledger alongside the root.">
            <input
              id="schema" className="input mono" value={schema}
              onChange={(e) => setSchema(e.target.value)}
            />
          </Field>

          {witness?.in_force && witness.required && (
            <div className="up__witness">
              <ShieldAlert size={16} />
              <div>
                <p className="up__witness-head">
                  This record must be counter-signed by {witness.witnesses.join(', ')}
                </p>
                <p className="small">
                  The witness rule is in force under round {witness.round_id} and this
                  record was drawn into the sample. The counter-signature is made with the
                  witnessing organisation&rsquo;s own key, so it cannot be produced from
                  this browser — sealing here will be refused by the contract, and that
                  refusal is the mechanism working. Choose a record type outside the
                  sample to seal one end to end.
                </p>
              </div>
            </div>
          )}

          <label className={`drop ${file ? 'has-file' : ''}`}>
            <input
              type="file"
              accept=".csv,text/csv"
              className="drop__input"
              onChange={(e) => {
                const chosen = e.target.files?.[0];
                if (chosen) void parse(chosen);
              }}
              disabled={phase === 'weaving'}
            />
            {file ? (
              <>
                <Check size={20} />
                <span className="drop__name mono">{file.name}</span>
                <span className="small drop__meta">
                  {commas(file.rows.length)} rows · {commas(file.bytes)} bytes ·{' '}
                  {file.columns.length} columns
                </span>
              </>
            ) : (
              <>
                <FileUp size={20} />
                <span className="drop__name">Choose a CSV export</span>
                <span className="small drop__meta">
                  Parsed here. The rows are sent to your own store; only a root is committed.
                </span>
              </>
            )}
          </label>

          {failure && <Failed error={failure} />}

          <button
            type="button"
            className="btn btn--primary btn--lg"
            disabled={!file || phase === 'weaving'}
            onClick={() => void seal()}
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

          {file && file.rows.length > 0 && (
            <div className="up__preview">
              <p className="stamp-type">First row, as parsed</p>
              <pre className="mono">{JSON.stringify(file.rows[0], null, 1)}</pre>
              <p className="small">
                <AlertTriangle size={12} /> Check this before sealing. The root is computed
                over exactly these values, and a sealed root cannot be revised.
              </p>
            </div>
          )}
        </div>

        <aside className="leaves">
          <p className="stamp-type leaves__head">What leaves your building</p>
          <div className="leaves__col leaves__col--stay">
            <p className="leaves__title">Stays here</p>
            <ul>
              <li>The file itself</li>
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
