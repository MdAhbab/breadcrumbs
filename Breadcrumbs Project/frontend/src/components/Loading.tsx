import './loading.css';

/**
 * The boot screen's small twin, for anything that arrives after the shell.
 *
 * Same mark, same thread, same rhythm — a loading state should look like the
 * product it is loading, not like a generic spinner borrowed from elsewhere.
 */
export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <span className="loading__thread"><i /></span>
      <span className="stamp-type loading__label">{label}</span>
    </div>
  );
}
