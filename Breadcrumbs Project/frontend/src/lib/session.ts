import { useCallback, useSyncExternalStore } from 'react';

import { ROLES, type Role, type RoleId } from './data';

const KEY = 'breadcrumbs.role';
const listeners = new Set<() => void>();

function read(): RoleId | null {
  try {
    const v = localStorage.getItem(KEY);
    return v && ROLES.some((r) => r.id === v) ? (v as RoleId) : null;
  } catch {
    // Private window, or site data blocked. Not an error — just no session.
    return null;
  }
}

let current: RoleId | null = read();

function emit() {
  listeners.forEach((l) => l());
}

export function signIn(id: RoleId) {
  current = id;
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* session lives for this page only */
  }
  emit();
}

export function signOut() {
  current = null;
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* nothing to do */
  }
  emit();
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** The signed-in role, or null. Reactive across the whole tree. */
export function useSession(): { role: Role | null; signIn: typeof signIn; signOut: typeof signOut } {
  const id = useSyncExternalStore(subscribe, () => current, () => null);
  const doSignIn = useCallback(signIn, []);
  const doSignOut = useCallback(signOut, []);
  return {
    role: id ? ROLES.find((r) => r.id === id)! : null,
    signIn: doSignIn,
    signOut: doSignOut,
  };
}
