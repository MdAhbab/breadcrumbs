import { useCallback, useSyncExternalStore } from 'react';

import {
  api,
  clearCredentials,
  setCredentials,
  setUnauthorizedHandler,
  storedRole,
  type RoleId,
  type RoleOption,
} from './api';

/**
 * Who is signed in.
 *
 * The session now holds a real bearer token issued by the API, because every
 * scoping rule in this product is enforced server-side against that token. The
 * previous version kept a role string in localStorage and asked the server
 * nothing, which meant the interface's idea of "you may not see this" and the
 * ledger's idea of it were two separate opinions.
 *
 * The sign-in *experience* is unchanged and deliberately thin: pick a role, go.
 * The API's two-step verification accepts any six-digit code and says so, so
 * the client supplies one rather than staging a credential prompt that checks
 * nothing. What is not simulated is the authorization that follows.
 */

const PROFILE_KEY = 'breadcrumbs.profile';

export interface Session {
  id: RoleId;
  label: string;
  org: string;
  mspId: string;
  person: string;
  summary: string;
  landing: string;
  /** The layout grammar this role's dashboard uses. Interface copy. */
  instrument: string;
}

/** The name each role's workspace goes by. Presentation, not data. */
export const INSTRUMENT: Record<RoleId, string> = {
  factory: 'The Loom Floor',
  buyer: 'The Lightbox',
  auditor: 'The Bench',
  consortium: 'The Chamber',
  regulator: 'The Observatory',
};

const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

function readProfile(): Session | null {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (!raw || !storedRole()) return null;
    return JSON.parse(raw) as Session;
  } catch {
    // Private window, blocked storage, or a stale shape. Not an error.
    return null;
  }
}

let current: Session | null = readProfile();

function set(next: Session | null) {
  current = next;
  try {
    if (next) localStorage.setItem(PROFILE_KEY, JSON.stringify(next));
    else localStorage.removeItem(PROFILE_KEY);
  } catch {
    /* the session lives for this page only */
  }
  emit();
}

/**
 * Exchange a role for a token, then ask the API who that makes us.
 *
 * The MSP identity comes back from `/api/auth/me` rather than being assumed
 * here: it is the identity the ledger will actually see, and the interface
 * should print the server's answer, not its own guess.
 */
export async function signIn(role: RoleOption): Promise<string> {
  // Any six digits are accepted and the sign-in screen says so.
  const token = await api.signIn(role.role, '000000');
  setCredentials(token.access_token, token.role);
  const me = await api.me();
  set({
    id: token.role,
    label: me.label,
    org: token.org,
    mspId: me.msp_id,
    person: token.person,
    summary: role.summary,
    landing: token.landing,
    instrument: INSTRUMENT[token.role],
  });
  return token.landing;
}

export function signOut(): void {
  clearCredentials();
  set(null);
}

// A rejected token is the one case where the client must give up its session
// without being asked to: the server has already decided.
setUnauthorizedHandler(() => set(null));

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function useSession(): {
  role: Session | null;
  signIn: typeof signIn;
  signOut: typeof signOut;
} {
  const role = useSyncExternalStore(subscribe, () => current, () => null);
  return {
    role,
    signIn: useCallback(signIn, []),
    signOut: useCallback(signOut, []),
  };
}
