import { useSyncExternalStore } from 'react';

import { api, type RequestableField } from './api';

/**
 * A column's name, as a person would say it.
 *
 * `net_pay_bdt` is what the file calls it. "Net pay (BDT)" is what it means,
 * and six different screens need the translation: the buyer's request form and
 * its list, the factory's inbox and its access page, the auditor's table and
 * the record page.
 *
 * One module-level fetch rather than a `useApi` in each of them, because six
 * components mounting six identical requests for a table that never changes
 * within a session is a waste, and because a labeller that is sometimes ready
 * and sometimes not produces screens that disagree with each other.
 *
 * Until it arrives, and if it never does, the raw column name is returned. A
 * missing label should cost a nicety, never a screen.
 */

type Table = Record<string, RequestableField[]>;

let table: Table | null = null;
let started = false;
const listeners = new Set<() => void>();

function load() {
  if (started) return;
  started = true;
  api.recordFields()
    .then((t) => {
      table = t;
      listeners.forEach((l) => l());
    })
    .catch(() => {
      // Signed out, or the caller may not read records. Raw names it is.
    });
}

function subscribe(cb: () => void) {
  load();
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export type FieldLabel = (recordType: string, field: string) => string;

export function useFieldLabel(): FieldLabel {
  const current = useSyncExternalStore(subscribe, () => table, () => null);
  return (recordType, field) =>
    current?.[recordType]?.find((f) => f.name === field)?.label ?? field;
}

/** Forget the table, so the next reader fetches it under the new identity. */
export function resetFieldLabels(): void {
  table = null;
  started = false;
  listeners.forEach((l) => l());
}
