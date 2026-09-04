import { AlertTriangle, Lock, Unlock } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { ApiError, api, recordLabel, type LedgerRecord, type PeriodSeal } from '../lib/api';
import { commas, longDate, period as periodName } from '../lib/format';
import { Failed } from './states';
import './mechanisms.css';

/**
 * Closing a period, reopening one, and closing it again.
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
 *
 * And then it was a trap. A reopened bucket counted as sealed for the
 * open-periods filter, so it was never offered a close button; `amendSeal` was
 * defined in the API client and called from nowhere; and this component
 * rendered a banner saying N periods were reopened and not yet re-sealed while
 * offering no way to re-seal one. The chaincode's own docstring names that
 * failure: the error message described a door that was not there.
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
  const [amending, setAmending] = useState<string | null>(null);
  const [amendReason, setAmendReason] = useState('');
  const [picked, setPicked] = useState<Record<string, string[]>>({});

  // Buckets the ledger holds records for but has never closed. A reopened
  // bucket is not one of these — it has a seal, it is mid-revision, and it
  // belongs in the section below with the amendment control.
  const known = new Set(seals.map((s) => s.bucket));
  const open = new Map<string, LedgerRecord[]>();
  for (const record of records) {
    if (known.has(record.bucket)) continue;
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
      setAmending(null);
      setReason('');
      setAmendReason('');
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

  /**
   * The records an amendment would be adding.
   *
   * A seal carries a count and a root, never a list, so the membership it was
   * closed with cannot be read back off it. What can be read is when it was
   * reopened — and the record an amendment exists for is by definition one
   * committed after that. Anything else in the bucket was already inside the
   * seal, and naming it as "added" would put a false claim on the chain.
   */
  const lateIn = (s: PeriodSeal): LedgerRecord[] => {
    const since = s.reopenings?.[s.reopenings.length - 1]?.reopened_at ?? s.sealed_at;
    return records
      .filter((r) => r.bucket === s.bucket && r.committed_at >= since)
      .sort((a, b) => a.record_id.localeCompare(b.record_id));
  };

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

      {/* -- reopened, waiting to be closed again --------------------------- */}
      {reopened.length > 0 && (
        <>
          <p className="stamp-type sealact__head">Reopened, waiting to be re-sealed</p>
          <ul className="sealact__list">
            {reopened.map((s) => {
              const late = lateIn(s);
              const chosen = picked[s.bucket] ?? late.map((r) => r.record_id);
              const last = s.reopenings?.[s.reopenings.length - 1];
              const [, , , per] = s.bucket.split('|');
              return (
                <li key={s.bucket} className="sealact__reo">
                  <div>
                    <p className="sealact__what">
                      {recordLabel(s.record_type)} · {s.site} · {periodName(s.period)}
                    </p>
                    <p className="small sealact__meta">
                      Sealed at {commas(s.record_count)} record
                      {s.record_count === 1 ? '' : 's'}, version {s.version}. Reopened
                      {last && <> on {longDate(last.reopened_at)}</>}
                      {last?.reason && <>: {last.reason}</>}. The ledger now holds{' '}
                      {commas(records.filter((r) => r.bucket === s.bucket).length)} for this
                      period.
                    </p>
                  </div>

                  {late.length === 0 ? (
                    <p className="small sealact__meta">
                      Nothing has been committed to this period since it was reopened, and
                      a correction must add at least one record. Naming one that was
                      already inside the seal would be a false claim on the chain. Commit
                      the late record first, then re-seal.{' '}
                      <Link
                        to={
                          '/factory/upload?type=' + encodeURIComponent(s.record_type)
                          + '&period=' + encodeURIComponent(per)
                          + '&site=' + encodeURIComponent(s.site)
                        }
                      >
                        Seal a record
                      </Link>
                      .
                    </p>
                  ) : amending === s.bucket ? (
                    <div className="sealact__reopen">
                      <fieldset className="sealact__adds">
                        <legend className="stamp-type">
                          Records committed since the reopening
                        </legend>
                        {late.map((r) => (
                          <label key={r.record_id} className="sealact__add">
                            <input
                              type="checkbox"
                              checked={chosen.includes(r.record_id)}
                              onChange={(e) =>
                                setPicked({
                                  ...picked,
                                  [s.bucket]: e.target.checked
                                    ? [...chosen, r.record_id]
                                    : chosen.filter((id) => id !== r.record_id),
                                })
                              }
                            />
                            <span className="mono">{r.record_id}</span>
                            <span className="small sealact__meta">
                              {commas(r.row_count)} rows · committed {longDate(r.committed_at)}
                            </span>
                          </label>
                        ))}
                      </fieldset>
                      <input
                        className="input"
                        placeholder="Why was this record late?"
                        value={amendReason}
                        onChange={(e) => setAmendReason(e.target.value)}
                      />
                      <div className="sealact__actions">
                        <button
                          type="button"
                          className="btn btn--primary btn--sm"
                          disabled={
                            amendReason.trim().length < 8
                            || chosen.length === 0
                            || busy === s.bucket
                          }
                          onClick={() =>
                            void act(s.bucket, () =>
                              api.amendSeal(s.bucket, chosen, amendReason.trim()),
                            )
                          }
                        >
                          <Lock size={13} />
                          {busy === s.bucket ? 'Amending…' : 'Amend and re-seal'}
                        </button>
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm"
                          onClick={() => { setAmending(null); setAmendReason(''); }}
                        >
                          Cancel
                        </button>
                      </div>
                      <p className="small sealact__meta">
                        The seal it has now stays in its own history with its own count and
                        root; this writes the next version over it. A period that has been
                        amended four times says so to anyone who looks, and that visibility
                        is the point rather than a side effect.
                      </p>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn btn--primary btn--sm"
                      onClick={() => { setAmending(s.bucket); setAmendReason(''); }}
                    >
                      <Lock size={13} /> Amend and re-seal
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </>
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
          <p className="small sealact__meta">
            Nothing else changes yet. Reopening records the intent; the period is closed
            again by committing the late record and amending, both of which stay visible.
          </p>
        </div>
      )}
    </div>
  );
}
