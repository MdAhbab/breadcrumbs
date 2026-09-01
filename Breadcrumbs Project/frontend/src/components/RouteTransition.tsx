import gsap from 'gsap';
import {
  useEffect, useLayoutEffect, useRef, useState, type ReactNode,
} from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';

import { EASE, ROUTE } from '../lib/motion';
import { useReducedMotion } from '../lib/useMotionPref';
import './routetransition.css';

/**
 * Navigation, as a thread being laid.
 *
 * A brass thread draws itself along the top edge while the page changes
 * underneath — the same gesture as the boot screen and the Suspense fallback,
 * so one mark means "something is loading" everywhere in the product.
 *
 * It draws from the leading edge: left to right going forward, right to left
 * going back. That keeps the direction of travel without a full-height bar
 * crossing the viewport, which reads as a scanner rather than a transition.
 *
 * The thread exists only for the 520ms of the navigation and unmounts with the
 * timeline. Nothing from this component is on screen at rest, and
 * `prefers-reduced-motion` swaps instantly without mounting it at all.
 */

interface Pending {
  key: string;
  node: ReactNode;
  back: boolean;
}

export function RouteTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navType = useNavigationType();
  const reduced = useReducedMotion();

  const stage = useRef<HTMLDivElement>(null);
  const run = useRef<HTMLSpanElement>(null);

  // The rendered children lag the location by one transition, so the outgoing
  // page stays painted while the thread draws.
  const [shown, setShown] = useState({ key: location.key, node: children });
  const [pending, setPending] = useState<Pending | null>(null);

  useLayoutEffect(() => {
    // Same route, new children: a state change rather than a navigation.
    if (location.key === shown.key) setShown((s) => ({ ...s, node: children }));
  }, [children, location.key, shown.key]);

  useEffect(() => {
    if (location.key === shown.key || pending?.key === location.key) return;

    // A replace is a correction, not a journey — a guard redirecting to the
    // sign-in should not look like the reader chose to go there.
    if (reduced || navType === 'REPLACE') {
      setShown({ key: location.key, node: children });
      return;
    }

    setPending({ key: location.key, node: children, back: navType === 'POP' });
    // `children` is intentionally omitted: it changes on every render, and a
    // journey starts only when the route itself changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key, navType, reduced]);

  useLayoutEffect(() => {
    if (!pending || !run.current || !stage.current) return;

    const tl = gsap.timeline({ onComplete: () => setPending(null) });

    tl
      // 1. The thread draws, quickly at first and then settling, the way a
      //    progress indicator behaves rather than a constant-speed wipe.
      .fromTo(
        run.current,
        { scaleX: 0, opacity: 1 },
        { scaleX: 1, duration: ROUTE * 0.72, ease: EASE.out },
        0,
      )
      // 2. The outgoing page clears.
      .to(stage.current, { opacity: 0, duration: ROUTE * 0.24, ease: EASE.in }, 0)
      // 3. Swap at the trough, and the new page comes up straight away. Every
      //    step carries an absolute position: appended steps would queue behind
      //    the thread, which is the longest tween on the timeline.
      .add(() => setShown({ key: pending.key, node: pending.node }), ROUTE * 0.24)
      .fromTo(
        stage.current,
        { opacity: 0 },
        { opacity: 1, duration: ROUTE * 0.42, ease: EASE.out },
        ROUTE * 0.26,
      )
      .to(run.current, { opacity: 0, duration: ROUTE * 0.26, ease: EASE.out }, ROUTE * 0.74);

    // A dead man's handle. The timeline is driven by requestAnimationFrame, and
    // a throttled tab — backgrounded, occluded, or a browser being aggressive —
    // stops rAF entirely. The page would then sit at opacity 0 for as long as
    // that lasted, which is a blank screen caused by a decoration. If the
    // timeline has not finished well after it should have, finish it.
    const deadline = window.setTimeout(() => tl.progress(1), ROUTE * 1000 + 700);

    return () => {
      window.clearTimeout(deadline);
      tl.kill();
      gsap.set(stage.current, { clearProps: 'all' });
    };
  }, [pending]);

  return (
    <div className="rtwrap">
      {pending && (
        <div
          className={`rthread ${pending.back ? 'rthread--back' : ''}`}
          role="progressbar"
          aria-label="Loading"
        >
          <span className="rthread__run" ref={run} />
        </div>
      )}

      <div className={`rtstage ${pending ? 'is-moving' : ''}`} ref={stage}>
        {shown.node}
      </div>
    </div>
  );
}
