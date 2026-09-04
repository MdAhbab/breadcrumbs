import { AlertTriangle, Lock, Unlock } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { ApiError, api, recordLabel, type LedgerRecord, type PeriodSeal } from '../lib/api';
import { commas, longDate, period as periodName } from '../lib/format';
import { Failed } from './states';
import { Drawer, DrawerHead } from './ui';
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
 *
 * Every form here now opens in a panel at the right rather than unfolding
 * inside the row it belongs to. Three lists live on this screen and each row of
 * each of them can open a form; inline, pressing one pushed everything below it
 * down the page, and closing a month — which is irreversible in the only sense
 * that matters, since undoing it is a permanent, counted reopening — happened
 * on a single unguarded click with no statement of what was about to be fixed.
 * The panel is where that statement goes.
 */
type Panel =
  | { kind: 'close' | 'reopen' | 'amend'; bucket: string }
  | null;

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
  const [panel, setPanel] = useState<Panel>(null);
  const [reason, setReason] = useState('');
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
      setPanel(null);
      setReason('');
      onChange();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'that did not work'));
    } finally {
      setBusy(null);
    }
  };

  const openPanel = (kind: 'close' | 'reopen' | 'amend', bucket: string) => {
    setFailure(null);
    setReason('');
    setPanel({ kind, bucket });
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

  const inBucket = (bucket: string) => records.filter((r) => r.bucket === bucket);
  const sealOf = (bucket: string) => seals.find((s) => s.bucket === bucket) ?? null;
  const nameOf = (bucket: string) => {
    const [, site, recordType, per] = bucket.split('|');
    return `${recordLabel(recordType)} · ${site} · ${periodName(per)}`;
  };

  return (
    <div className="sealact">
      {failure && !panel && <Failed error={failure} />}

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
                        Upload a document
                      </Link>
                      .
                    </p>
                  ) : (
                    <button
                      type="button"
                      className="btn btn--primary btn--sm"
                      onClick={() => openPanel('amend', s.bucket)}
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
                  onClick={() => openPanel('close', bucket)}
                >
                  <Lock size={13} /> Close this period
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

      <select
        className="input"
        value=""
        onChange={(e) => e.target.value && openPanel('reopen', e.target.value)}
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

      {/* -- the form, at the right ---------------------------------------- */}
      {panel && (
        <Drawer label={`${panel.kind} ${nameOf(panel.bucket)}`} onClose={() => setPanel(null)}>
          <DrawerHead
            eyebrow={nameOf(panel.bucket)}
            title={
              panel.kind === 'close' ? 'Close this month'
                : panel.kind === 'reopen' ? 'Reopen this month'
                  : 'Amend and re-seal'
            }
            onClose={() => setPanel(null)}
          />

          {failure && <Failed error={failure} />}

          {panel.kind === 'close' && (
            <ClosePanel
              bucket={panel.bucket}
              held={inBucket(panel.bucket)}
              busy={busy === panel.bucket}
              onConfirm={() => void seal(panel.bucket, inBucket(panel.bucket))}
              onCancel={() => setPanel(null)}
            />
          )}

          {panel.kind === 'reopen' && (
            <ReopenPanel
              seal={sealOf(panel.bucket)}
              reason={reason}
              onReason={setReason}
              busy={busy === panel.bucket}
              onConfirm={() =>
                void act(panel.bucket, () => api.reopenSeal(panel.bucket, reason.trim()))}
              onCancel={() => setPanel(null)}
            />
          )}

          {panel.kind === 'amend' && (() => {
            const s = sealOf(panel.bucket);
            if (!s) return null;
            const late = lateIn(s);
            const chosen = picked[s.bucket] ?? late.map((r) => r.record_id);
            return (
              <AmendPanel
                seal={s}
                late={late}
                chosen={chosen}
                onPick={(ids) => setPicked({ ...picked, [s.bucket]: ids })}
                reason={reason}
                onReason={setReason}
                busy={busy === panel.bucket}
                onConfirm={() =>
                  void act(panel.bucket, () =>
                    api.amendSeal(panel.bucket, chosen, reason.trim()))}
                onCancel={() => setPanel(null)}
              />
            );
          })()}
        </Drawer>
      )}
    </div>
  );
}

/**
 * Closing a month, with the list it is about to fix in front of you.
 *
 * This was one unguarded press. What it does is fix the membership of a period
 * permanently — the only way back is a reopening, which is itself permanent and
 * counted on the seal — and the factory was not shown which records were about
 * to be inside it.
 */
function ClosePanel({
  bucket, held, busy, onConfirm, onCancel,
}: {
  bucket: string;
  held: LedgerRecord[];
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [, , , per] = bucket.split('|');
  return (
    <div className="sealpanel">
      <p className="sealpanel__lede">
        Closing fixes exactly which records {periodName(per)} contains. After this,
        nothing can be added to it quietly: a late record has to come in as an open
        correction, with a reason, and the seal counts how many times that has happened.
      </p>

      <p className="stamp-type sealpanel__label">
        {commas(held.length)} record{held.length === 1 ? '' : 's'} will be sealed in
      </p>
      <ul className="sealpanel__ids">
        {held.map((r) => (
          <li key={r.record_id}>
            <span className="mono">{r.record_id}</span>
            <span className="small sealact__meta">
              {commas(r.row_count)} rows · committed {longDate(r.committed_at)}
            </span>
          </li>
        ))}
      </ul>

      <div className="sealpanel__actions">
        <button
          type="button"
          className="btn btn--primary btn--sm"
          disabled={busy || held.length === 0}
          onClick={onConfirm}
        >
          <Lock size={13} />
          {busy ? 'Closing…' : `Close ${periodName(per)} at ${commas(held.length)}`}
        </button>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onCancel}>
          Cancel
        </button>
      </div>

      <p className="small sealact__meta">
        The count and a root over those identifiers go onto the ledger. That is what a
        buyer later checks its disclosure against, which is why it has to be fixed before
        anything is released rather than after.
      </p>
    </div>
  );
}

function ReopenPanel({
  seal, reason, onReason, busy, onConfirm, onCancel,
}: {
  seal: PeriodSeal | null;
  reason: string;
  onReason: (v: string) => void;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="sealpanel">
      <p className="sealpanel__lede">
        {seal
          ? `Sealed at ${commas(seal.record_count)} record${seal.record_count === 1 ? '' : 's'}, `
            + `version ${seal.version}, on ${longDate(seal.sealed_at)}.`
          : 'This period is closed.'}{' '}
        Reopening is permanent and is counted on the seal for anyone who looks at it
        afterwards.
      </p>

      <label className="sealpanel__field">
        <span className="stamp-type">Why is this period being reopened?</span>
        <input
          className="input"
          placeholder="A late payroll register for the Ashulia line…"
          value={reason}
          onChange={(e) => onReason(e.target.value)}
        />
      </label>

      <div className="sealpanel__actions">
        <button
          type="button"
          className="btn btn--danger btn--sm"
          disabled={reason.trim().length < 8 || busy}
          onClick={onConfirm}
        >
          <Unlock size={13} /> {busy ? 'Reopening…' : 'Reopen, permanently'}
        </button>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {reason.trim().length < 8 && (
        <p className="small sealact__meta">
          Write a reason. The contract requires one and it stays on the seal.
        </p>
      )}
      <p className="small sealact__meta">
        Nothing else changes yet. Reopening records the intent; the period is closed again
        by committing the late record and amending, both of which stay visible.
      </p>
    </div>
  );
}

function AmendPanel({
  seal, late, chosen, onPick, reason, onReason, busy, onConfirm, onCancel,
}: {
  seal: PeriodSeal;
  late: LedgerRecord[];
  chosen: string[];
  onPick: (ids: string[]) => void;
  reason: string;
  onReason: (v: string) => void;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="sealpanel">
      <p className="sealpanel__lede">
        Sealed at {commas(seal.record_count)} record{seal.record_count === 1 ? '' : 's'},
        version {seal.version}. Tick what is being added and say why it was late.
      </p>

      <fieldset className="sealact__adds">
        <legend className="stamp-type">Records committed since the reopening</legend>
        {late.map((r) => (
          <label key={r.record_id} className="sealact__add">
            <input
              type="checkbox"
              checked={chosen.includes(r.record_id)}
              onChange={(e) =>
                onPick(
                  e.target.checked
                    ? [...chosen, r.record_id]
                    : chosen.filter((id) => id !== r.record_id),
                )}
            />
            <span className="mono">{r.record_id}</span>
            <span className="small sealact__meta">
              {commas(r.row_count)} rows · committed {longDate(r.committed_at)}
            </span>
          </label>
        ))}
      </fieldset>

      <label className="sealpanel__field">
        <span className="stamp-type">Why was this record late?</span>
        <input
          className="input"
          placeholder="Received from the Ashulia line after the month was closed…"
          value={reason}
          onChange={(e) => onReason(e.target.value)}
        />
      </label>

      <div className="sealpanel__actions">
        <button
          type="button"
          className="btn btn--primary btn--sm"
          disabled={reason.trim().length < 8 || chosen.length === 0 || busy}
          onClick={onConfirm}
        >
          <Lock size={13} /> {busy ? 'Amending…' : 'Amend and re-seal'}
        </button>
        <button type="button" className="btn btn--ghost btn--sm" onClick={onCancel}>
          Cancel
        </button>
      </div>

      <p className="small sealact__meta">
        The seal it has now stays in its own history with its own count and root; this
        writes the next version over it. A period that has been amended four times says so
        to anyone who looks, and that visibility is the point rather than a side effect.
      </p>
    </div>
  );
}
