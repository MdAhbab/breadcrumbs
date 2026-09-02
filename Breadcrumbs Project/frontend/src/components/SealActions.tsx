import { AlertTriangle, Lock, Unlock } from 'lucide-react';
import { useState } from 'react';

import { ApiError, api, recordLabel, type LedgerRecord, type PeriodSeal } from '../lib/api';
import { commas, period as periodName } from '../lib/format';
import { Failed } from './states';
import './mechanisms.css';

/**
 * Closing a period, and reopening one.
 *
 * The interface could show seals without ever making one, and it did. But a
 * seal is the mechanism this whole product is about, and a screen that can only
 * display the result of an operation it cannot perform is a screenshot.
 *
 * Reopening is here for the same reason and is the more interesting half. It is
 * permanent, it is counted, and while a period is open the completeness check
 * refuses to answer with the old figure — it reports the period as mid-revision
 * instead. That honest state was reachable in the contract and unreachable from
 * the product.
 */
export function SealActions({
  records,
  seals,
  onChange,
}: {
  records: LedgerRecord[];
  seals: PeriodSeal[];
  onChange: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const [reason, setReason] = useState('');
  const [reopening, setReopening] = useState<string | null>(null);

  // Buckets the ledger holds records for but has never closed.
  const sealed = new Set(seals.map((s) => s.bucket));
  const open = new Map<string, LedgerRecord[]>();
  for (const record of records) {
    if (sealed.has(record.bucket)) continue;
    const held = open.get(record.bucket) ?? [];
    held.push(record);
    open.set(record.bucket, held);
  }

  const act = async (key: string, run: () => Promise<unknown>) => {
    setBusy(key);
    setFailure(null);
    try {
      await run();
      setReopening(null);
      setReason('');
      onChange();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'that did not work'));
    } finally {
      setBusy(null);
    }
  };

  const seal = (bucket: string, held: LedgerRecord[]) => {
    const [, site, recordType, per] = bucket.split('|');
    return act(bucket, () =>
      api.sealPeriod({
        site,
        record_type: recordType,
        period: per,
        record_ids: held.map((r) => r.record_id).sort(),
      }),
    );
  };

  const reopened = seals.filter((s) => s.status === 'reopened');

  return (
    <div className="sealact">
      {failure && <Failed error={failure} />}

      {reopened.length > 0 && (
        <div className="sealact__warn">
          <AlertTriangle size={15} />
          <p className="small">
            {reopened.length} period{reopened.length === 1 ? ' is' : 's are'} reopened and
            not yet re-sealed. Until they are, a completeness check on them reports the
            membership as mid-revision rather than serving the old count.
          </p>
        </div>
      )}

      <p className="stamp-type sealact__head">Open periods</p>
      {open.size === 0 ? (
        <p className="small sealact__none">
          Every period the ledger holds records for has been closed.
        </p>
      ) : (
        <ul className="sealact__list">
          {[...open.entries()].sort().map(([bucket, held]) => {
            const [, site, recordType, per] = bucket.split('|');
            return (
              <li key={bucket} className="sealact__row">
                <div>
                  <p className="sealact__what">
                    {recordLabel(recordType)} · {site} · {periodName(per)}
                  </p>
                  <p className="small sealact__meta">
                    {commas(held.length)} records on the ledger, never closed
                  </p>
                </div>
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  disabled={busy === bucket}
                  onClick={() => void seal(bucket, held)}
                >
                  <Lock size={13} /> {busy === bucket ? 'Sealing…' : 'Close this period'}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <p className="stamp-type sealact__head">Reopen a closed period</p>
      <p className="small sealact__meta">
        Only if a genuinely late record has to come in. Reopening is permanent, it is
        counted on the seal, and the reason is recorded before anything changes.
      </p>

      {reopening === null ? (
        <select
          className="input"
          value=""
          onChange={(e) => e.target.value && setReopening(e.target.value)}
        >
          <option value="">Choose a period…</option>
          {seals
            .filter((s) => s.status === 'sealed')
            .map((s) => (
              <option key={s.bucket} value={s.bucket}>
                {s.site} · {recordLabel(s.record_type)} · {periodName(s.period)} ·{' '}
                {s.record_count} records
              </option>
            ))}
        </select>
      ) : (
        <div className="sealact__reopen">
          <p className="mono small">{reopening}</p>
          <input
            className="input"
            placeholder="Why is this period being reopened?"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="sealact__actions">
            <button
              type="button"
              className="btn btn--danger btn--sm"
              disabled={reason.trim().length < 8 || busy === reopening}
              onClick={() => void act(reopening, () => api.reopenSeal(reopening, reason.trim()))}
            >
              <Unlock size={13} />
              {busy === reopening ? 'Reopening…' : 'Reopen, permanently'}
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => { setReopening(null); setReason(''); }}
            >
              Cancel
            </button>
          </div>
          {reason.trim().length < 8 && (
            <p className="small sealact__meta">
              Write a reason. The contract requires one and it stays on the seal.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
