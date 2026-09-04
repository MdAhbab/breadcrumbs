import { SlidersHorizontal } from 'lucide-react';
import type { ReactNode } from 'react';

import { useDetail } from '../lib/detail';
import './tech.css';

/**
 * The machinery, shown only to a reader who asked for it.
 *
 * Wrap anything that is true but unactionable for a stakeholder: roots,
 * transaction identifiers, block numbers, schema versions, MSP identities. In
 * plain mode it is not rendered at all — not greyed out, not collapsed behind a
 * chevron the reader has to wonder about. A screen in plain mode should look
 * like it was designed for that reader, not like a technical screen with parts
 * missing.
 */
export function Tech({ children }: { children: ReactNode }) {
  const { technical } = useDetail();
  if (!technical) return null;
  return <>{children}</>;
}

/**
 * The inverse: copy that only makes sense to someone *not* seeing the
 * machinery. Lets a page explain a root in one plain sentence, and drop that
 * sentence once the root itself is on screen.
 */
export function Plain({ children }: { children: ReactNode }) {
  const { technical } = useDetail();
  if (technical) return null;
  return <>{children}</>;
}

/**
 * The one control that switches between them.
 *
 * Deliberately worded as what the reader gets rather than who they are — "show
 * technical detail" is a decision anyone can make about the next screen, where
 * "engineer mode" asks them to classify themselves first.
 */
export function DetailToggle({
  compact = false, dark = false,
}: { compact?: boolean; dark?: boolean }) {
  const { technical, toggle } = useDetail();
  return (
    <button
      type="button"
      className={`dtoggle ${technical ? 'is-on' : ''} ${compact ? 'dtoggle--compact' : ''} ${
        dark ? 'dtoggle--dark' : ''
      }`}
      onClick={toggle}
      aria-pressed={technical}
      title={
        technical
          ? 'Hiding hashes, block numbers and identifiers'
          : 'Showing hashes, block numbers and identifiers'
      }
    >
      <SlidersHorizontal size={13} strokeWidth={1.75} />
      <span className="dtoggle__label">Technical detail</span>
      <span className="dtoggle__track" aria-hidden="true"><span className="dtoggle__knob" /></span>
    </button>
  );
}
