import { AlertTriangle, Lock, RefreshCw, ServerCrash } from 'lucide-react';
import type { ReactNode } from 'react';

import type { ApiError } from '../lib/api';
import './states.css';

/**
 * What a screen shows when it is not showing data.
 *
 * These are shared because the alternative is fifteen pages each inventing
 * their own idea of "nothing here", and because the distinctions matter: a
 * refusal, an outage and a genuinely empty result are three different facts
 * about the system and a spinner-then-blank collapses them into one.
 */

export function Pending({ label = 'Reading the ledger' }: { label?: string }) {
  return (
    <div className="state state--pending" role="status" aria-live="polite">
      <span className="state__thread" aria-hidden="true" />
      <p className="stamp-type state__label">{label}</p>
    </div>
  );
}

/**
 * A failure, told apart by kind.
 *
 * A 403 is not an error in the usual sense — it is the capability table doing
 * its job, and the message is the contract's own explanation of what this role
 * may do instead. It gets a lock and the sentence, not a red alarm.
 */
export function Failed({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const offline = error.code === 'NO_BACKEND' || error.status === 0;
  const denied = error.denied;
  // Not a failure: the API is up and building the demo world, and the client is
  // already retrying. It gets the loading mark rather than an alarm.
  const building = error.code === 'WORLD_BUILDING';

  if (building) {
    return (
      <div className="state state--pending" role="status" aria-live="polite">
        <span className="state__thread" aria-hidden="true" />
        <div className="state__body">
          <p className="stamp-type state__kind">Building the ledger</p>
          <p className="state__message">{error.message}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`state state--failed ${denied ? 'is-denied' : ''}`} role="alert">
      <span className="state__icon" aria-hidden="true">
        {denied ? <Lock size={18} /> : offline ? <ServerCrash size={18} /> : <AlertTriangle size={18} />}
      </span>
      <div className="state__body">
        <p className="stamp-type state__kind">
          {denied ? 'Not permitted for this role' : offline ? 'The API is not answering' : 'That did not work'}
        </p>
        <p className="state__message">{error.message}</p>
        {error.code && !offline && <p className="mono small dim">{error.code}</p>}
      </div>
      {onRetry && !denied && (
        <button type="button" className="btn btn--ghost btn--sm" onClick={onRetry}>
          <RefreshCw size={14} /> Try again
        </button>
      )}
    </div>
  );
}

/** Nothing to show, and the reason why — never a bare blank. */
export function Empty({ title, detail }: { title: string; detail?: ReactNode }) {
  return (
    <div className="state state--empty">
      <p className="state__kind stamp-type">{title}</p>
      {detail && <p className="state__message">{detail}</p>}
    </div>
  );
}

/**
 * The whole pattern in one component.
 *
 * `children` is only called with data, so a page never writes `data!` or guards
 * a null it has already checked three lines above.
 */
export function Result<T>({
  query,
  children,
  pendingLabel,
  empty,
  isEmpty,
}: {
  query: { data: T | null; error: ApiError | null; loading: boolean; reload: () => void };
  children: (data: T) => ReactNode;
  pendingLabel?: string;
  empty?: { title: string; detail?: ReactNode };
  isEmpty?: (data: T) => boolean;
}) {
  if (query.loading && query.data === null) return <Pending label={pendingLabel} />;
  if (query.error) return <Failed error={query.error} onRetry={query.reload} />;
  if (query.data === null) return <Pending label={pendingLabel} />;
  if (empty && isEmpty?.(query.data)) return <Empty title={empty.title} detail={empty.detail} />;
  return <>{children(query.data)}</>;
}
