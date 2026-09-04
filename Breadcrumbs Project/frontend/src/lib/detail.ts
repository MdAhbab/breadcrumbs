import { useCallback, useSyncExternalStore } from 'react';

/**
 * How much of the machinery to show.
 *
 * The product has two audiences with opposite needs. A merchandiser asking
 * whether a payroll figure is real needs one sentence and a verdict; an
 * engineer auditing the same claim needs the root, the siblings, the block and
 * the transaction. The previous interface served the second audience to both,
 * so every screen asked its reader to learn what a Merkle root is before it
 * would answer a yes/no question.
 *
 * So the hashes, identifiers, block numbers and schema versions are still all
 * there, and they are all one switch away — but "plain" is the default, and in
 * plain mode no screen shows a value the reader cannot act on.
 *
 * This is presentation only. Nothing here changes what is fetched, what is
 * proved, or what the contract enforces.
 */

export type Detail = 'plain' | 'technical';

const KEY = 'breadcrumbs.detail';

function read(): Detail {
  try {
    return localStorage.getItem(KEY) === 'technical' ? 'technical' : 'plain';
  } catch {
    // Private window or blocked storage. Plain is the safe default.
    return 'plain';
  }
}

let current: Detail = read();
const listeners = new Set<() => void>();

export function setDetail(next: Detail): void {
  if (next === current) return;
  current = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    /* the preference lives for this page only */
  }
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** The current level, and a setter. Server snapshot is plain. */
export function useDetail(): {
  detail: Detail;
  technical: boolean;
  setDetail: (d: Detail) => void;
  toggle: () => void;
} {
  const detail = useSyncExternalStore(subscribe, () => current, () => 'plain' as Detail);
  return {
    detail,
    technical: detail === 'technical',
    setDetail,
    toggle: useCallback(() => setDetail(current === 'plain' ? 'technical' : 'plain'), []),
  };
}
