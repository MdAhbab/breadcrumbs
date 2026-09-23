import { Brain, Search, TriangleAlert } from 'lucide-react';
import { useState } from 'react';

import { ApiError, api, type Screening as Result } from '../lib/api';
import { Failed } from './states';
import { Tech } from './Tech';
import './mechanisms.css';

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? 'n/a' : `${(v * 100).toFixed(1)}%`;

/**
 * What the shared AI model thinks of this document.
 *
 * The hardest panel in the product to get right, because it sits a few
 * centimetres below a cryptographic proof and the two are not the same kind of
 * fact. The proof is checkable by anyone and settles the question. This is a
 * guess, it is not on the ledger, it is not signed, and nobody is accountable
 * for it.
 *
 * So it is deliberately quiet, it is behind a button rather than running on
 * page load, and the measured error rates are shown beside the score every
 * time rather than being available on request. A screen that showed "94%
 * anomalous" in red with no denominator would be the most dishonest thing in
 * this product, and it would be the easiest to build.
 */
export function Screening({ recordId }: { recordId: string }) {
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.screen(recordId));
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err : new ApiError(0, 'the AI model failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="screen">
      {!result && (
        <div className="screen__ask">
          <Brain size={16} />
          <div>
            {/* The page heading already names this panel and says it is a guess. */}
            <p className="small screen__sub">
              Scores how unusual this document looks. The score is not saved on the ledger.
            </p>
          </div>
          <button
            type="button"
            className="btn btn--secondary btn--sm"
            onClick={() => void run()}
            disabled={busy}
          >
            <Search size={13} /> {busy ? 'Scoring…' : 'Get the score'}
          </button>
        </div>
      )}

      {error && <Failed error={error} onRetry={() => void run()} />}

      {result && !result.trained && (
        <div className="screen__ask">
          <TriangleAlert size={16} />
          <div>
            <p className="screen__title">No AI model is in use</p>
            <Tech><p className="small screen__sub">{result.reason}</p></Tech>
          </div>
        </div>
      )}

      {result && result.scored && (
        <div className={`screen__out ${result.flagged ? 'is-flagged' : 'is-quiet'}`}>
          <header className="screen__head">
            <div>
              <p className="screen__verdict">{result.verdict}</p>
              <p className="small screen__sub">
                Score {result.score?.toFixed(3)}. It flags {result.threshold?.toFixed(3)} or
                more.
                {result.likely_kind && <> Looks most like: {result.likely_kind}.</>}
              </p>
            </div>
            <span className="screen__bar" aria-hidden="true">
              <span
                className="screen__fill"
                style={{ width: `${Math.min(100, (result.score ?? 0) * 100)}%` }}
              />
              <span
                className="screen__tau"
                style={{ left: `${(result.threshold ?? 0) * 100}%` }}
              />
            </span>
          </header>

          <p className="screen__caveat">{result.caveat}</p>

          <div className="screen__rates">
            <Rate label="catches" value={pct(result.measured?.detection)} />
            <Rate label="flags clean documents" value={pct(result.measured?.false_positive)} />
            <Tech>
              <Rate label="balanced accuracy" value={pct(result.measured?.balanced_accuracy)} />
              <Rate label="over seeds" value={String(result.measured?.seeds ?? 'n/a')} />
            </Tech>
          </div>

          {result.blind_to && (
            <p className="small screen__blind">
              <TriangleAlert size={12} />
              <span>
                It is no better than guessing on <span className="mono">{result.blind_to.kind}</span>.{' '}
                {pct(result.blind_to.detection)} detection. {result.blind_to.why}
              </span>
            </p>
          )}

          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => setResult(null)}
          >
            Close
          </button>
        </div>
      )}
    </section>
  );
}

function Rate({ label, value }: { label: string; value: string }) {
  return (
    <div className="screen__rate">
      <span className="screen__n">{value}</span>
      <span className="stamp-type">{label}</span>
    </div>
  );
}
