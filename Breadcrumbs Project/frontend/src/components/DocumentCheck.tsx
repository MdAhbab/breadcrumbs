import { Check, Eye, Lock, Play, X } from 'lucide-react';
import { useState } from 'react';

import { ApiError, api, type Grant, type RecordPreview as Preview } from '../lib/api';
import { commas } from '../lib/format';
import { useApi } from '../lib/useApi';
import { Failed, Result } from './states';
import './documentcheck.css';

/**
 * A document, and the proof that it is real, on one screen.
 *
 * The previous version of this page asked for a grant, a row number and a
 * column name, then returned one value. That is the shape of the API, not the
 * shape of the question: nobody knows they want row 0 of anything. A buyer
 * opens what it was given, reads it, and wants to know whether it is true.
 *
 * So this is the document. Every row it holds, every column this account may
 * read, and a check against the ledger on each row that runs a real Merkle
 * proof and writes a real receipt. Nothing here is a summary of the proof
 * screen; it *is* the proof screen.
 */
type RowState = 'checking' | 'passed' | 'failed' | undefined;

export function DocumentCheck({ recordId }: { recordId: string }) {
  // The whole document, not a glance at it: you cannot check a figure you
  // cannot see.
  const preview = useApi(() => api.recordPreview(recordId, 500), [recordId]);
  const grants = useApi(() => api.grants(), []);

  const [state, setState] = useState<Record<number, RowState>>({});
  const [running, setRunning] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  // Only a column covered by a live permission can be proved: a receipt names
  // the exact figure it covers, and the contract refuses to write one outside
  // that. Reading is wider than proving, and the table says which is which.
  const provable: Grant[] = (grants.data ?? []).filter(
    (g) => g.record_id === recordId && g.status === 'active',
  );

  const checkRow = async (index: number) => {
    if (!provable.length) return;
    setState((s) => ({ ...s, [index]: 'checking' }));
    let ok = true;
    for (const grant of provable) {
      try {
        const proof = await api.proveRow({
          grant_id: grant.grant_id,
          record_id: recordId,
          row_index: index,
          field_name: grant.field_name,
          receipt_id: `vr-${grant.grant_id}-${index}-${Date.now().toString(36)}`,
        });
        if (!proof.verified) ok = false;
      } catch (err) {
        ok = false;
        if (err instanceof ApiError) setFailure(err);
      }
    }
    setState((s) => ({ ...s, [index]: ok ? 'passed' : 'failed' }));
    return ok;
  };

  const checkAll = async (count: number) => {
    setRunning(true);
    setFailure(null);
    for (let i = 0; i < count; i += 1) await checkRow(i);
    setRunning(false);
  };

  return (
    <section className="doc">
      <Result query={preview} pendingLabel="Opening the document">
        {(p: Preview) => {
          const checked = Object.values(state).filter((v) => v === 'passed').length;
          const failed = Object.values(state).filter((v) => v === 'failed').length;

          return (
            <>
              <header className="doc__head">
                <div>
                  <h2 className="doc__title">What you can see, and whether it is real</h2>
                  <p className="small doc__sub">
                    {commas(p.shown_rows)} row{p.shown_rows === 1 ? '' : 's'} ·{' '}
                    {p.readable_columns} of {p.total_columns} columns readable by you.
                    {provable.length > 0
                      ? ` Checking a row proves ${provable.length === 1
                        ? 'the figure' : `all ${provable.length} figures`} you hold on it `
                        + 'against the fingerprint the factory published.'
                      : ' Nothing here has been released to you to prove, so the check '
                        + 'is unavailable.'}
                  </p>
                </div>
                {provable.length > 0 && (
                  <button
                    type="button"
                    className="btn btn--primary btn--sm"
                    onClick={() => void checkAll(p.shown_rows)}
                    disabled={running}
                  >
                    <Play size={13} />
                    {running ? 'Checking…' : `Check all ${commas(p.shown_rows)} rows`}
                  </button>
                )}
              </header>

              {(checked > 0 || failed > 0) && (
                <p className={`doc__tally ${failed ? 'is-bad' : 'is-ok'}`}>
                  {failed === 0
                    ? `${commas(checked)} row${checked === 1 ? '' : 's'} checked against `
                      + 'the ledger. Every one matched.'
                    : `${commas(checked)} matched, ${commas(failed)} did not. `
                      + 'A row that does not match means the file was altered after it '
                      + 'was published.'}
                </p>
              )}

              {failure && <Failed error={failure} />}

              <div className="doc__scroll scroll-x">
                <table className="doc__table">
                  <thead>
                    <tr>
                      {provable.length > 0 && <th scope="col" className="doc__checkcol">Check</th>}
                      <th scope="col" className="doc__rowno">Row</th>
                      {p.columns.map((c) => (
                        <th
                          key={c.name}
                          scope="col"
                          className={c.visible ? '' : 'is-hidden'}
                          title={c.reason}
                        >
                          <span className="doc__th">
                            {c.visible
                              ? <Eye size={11} className="doc__eye" aria-hidden="true" />
                              : <Lock size={11} aria-hidden="true" />}
                            {c.label}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {p.rows.map((row, i) => {
                      const at = state[i];
                      return (
                        <tr key={i} className={at ? `is-${at}` : ''}>
                          {provable.length > 0 && (
                            <td className="doc__checkcol">
                              <button
                                type="button"
                                className={`doc__check is-${at ?? 'idle'}`}
                                onClick={() => void checkRow(i)}
                                disabled={running || at === 'checking'}
                                aria-label={`Check row ${i + 1} against the ledger`}
                              >
                                {at === 'passed' ? <Check size={12} strokeWidth={3} />
                                  : at === 'failed' ? <X size={12} strokeWidth={3} />
                                    : at === 'checking' ? '…'
                                      : 'check'}
                              </button>
                            </td>
                          )}
                          <td className="doc__rowno mono">{i + 1}</td>
                          {p.columns.map((c) => (
                            <td key={c.name} className={c.visible ? '' : 'is-hidden'}>
                              {c.visible ? (
                                cell(row[c.name])
                              ) : (
                                <span className="doc__redacted" title={c.reason}>███</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {p.total_rows > p.shown_rows && (
                <p className="small doc__note">
                  Showing {commas(p.shown_rows)} of {commas(p.total_rows)} rows.
                </p>
              )}
              <p className="small doc__note">
                The columns behind a padlock were never sent to your browser. Anything
                naming a person stays closed to everyone but the factory.
              </p>
            </>
          );
        }}
      </Result>
    </section>
  );
}

function cell(value: unknown) {
  if (value === null || value === undefined || value === '') return <span className="dim">empty</span>;
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (Array.isArray(value)) return value.length ? value.join(', ') : <span className="dim">none</span>;
  if (typeof value === 'number') {
    return <span className="doc__num">{value.toLocaleString('en-GB')}</span>;
  }
  return String(value);
}
