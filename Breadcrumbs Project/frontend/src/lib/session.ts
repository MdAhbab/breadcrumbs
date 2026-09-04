import { useCallback, useSyncExternalStore } from 'react';

import { resetFieldLabels } from './useFieldLabel';
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
  /** What this role's home screen is called, in the words it is called by. */
  workspace: string;
}

/**
 * The name each role's home screen goes by.
 *
 * These used to be invented ones — the Loom Floor, the Lightbox, the Bench, the
 * Chamber, the Observatory — which meant the navigation could not be read
 * without first being taught. A name is now a description of the job.
 */
export const WORKSPACE: Record<RoleId, string> = {
  factory: 'your records',
  buyer: 'your requests',
  auditor: 'your checks',
  consortium: 'governance',
  regulator: 'the overview',
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
  // The column table is scoped to whoever asked for it, so it cannot outlive
  // the session that fetched it.
  resetFieldLabels();
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
    workspace: WORKSPACE[token.role],
  });
  return token.landing;
}

/**
 * Sign in knowing only the role id.
 *
 * The guided tour moves between five people in nine steps, and asking it to
 * carry a full `RoleOption` for each would mean holding a second copy of the
 * role table in the client. It fetches the API's.
 */
export async function signInAs(id: RoleId): Promise<string> {
  const options = await api.roles();
  const option = options.find((o) => o.role === id);
  if (!option) throw new Error(`no such role: ${id}`);
  return signIn(option);
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
