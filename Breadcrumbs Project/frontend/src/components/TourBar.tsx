import { ArrowLeft, ArrowRight, ChevronDown, ChevronUp, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { signInAs, useSession } from '../lib/session';
import { TOUR, endTour, goToStep, startTour, stepsOf, useTour } from '../lib/tour';
import './tourbar.css';

/**
 * The guided run-through, as a bar along the foot of the page.
 *
 * It rides above every screen rather than replacing any of them, because the
 * thing being demonstrated is the product, not a slideshow of it. Each step
 * signs itself in as whoever that step belongs to, so the visitor is never
 * asked to work out that the story has changed hands four times.
 *
 * It folds down to a single line: the screen that most needs explaining — the
 * gate refusing a model — is also the one that most needs the room, and a demo
 * aid that covers the demo is worse than none.
 */
export function TourBar() {
  const { active, step, current, total, part, steps } = useTour();
  const { role } = useSession();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [folded, setFolded] = useState(false);
  const [moving, setMoving] = useState(false);

  // The bar is fixed, so the page beneath has to be told to end above it. A
  // body attribute rather than a wrapper class: the scrolling element is the
  // page's own, and it is a different element on every route.
  const showing = active && pathname !== '/';
  useEffect(() => {
    if (!showing) {
      delete document.body.dataset.tour;
      return;
    }
    document.body.dataset.tour = folded ? 'folded' : 'open';
    return () => { delete document.body.dataset.tour; };
  }, [showing, folded]);

  // The home page runs a pinned, scrubbed narrative that a fixed bar sits badly
  // over, and the tour never sends anyone there.
  if (!showing) return null;

  const go = async (to: number) => {
    if (to < 0 || to >= total || moving) return;
    const target = steps[to];
    setMoving(true);
    try {
      // Each step belongs to a person. Switching to them is the tour's job,
      // not the visitor's.
      if (target.role && target.role !== role?.id) await signInAs(target.role);
      goToStep(to);
      navigate(target.to);
    } catch {
      // A failed sign-in leaves the step where it is rather than advancing onto
      // a screen this session cannot read.
    } finally {
      setMoving(false);
    }
  };

  const last = step === total - 1;

  // Part one ends with an offer rather than a full stop. Part two is genuinely
  // optional: somebody who has seen the idea work may not want the tour of the
  // rest of the cupboards, and "Finish" is the bigger, plainer way out.
  const startMore = async () => {
    setMoving(true);
    try {
      const first = stepsOf('more')[0];
      if (first.role && first.role !== role?.id) await signInAs(first.role);
      startTour('more');
      navigate(first.to);
    } finally {
      setMoving(false);
    }
  };

  return (
    <div
      className={`tourbar ${folded ? 'is-folded' : ''}`}
      role="complementary"
      aria-label="Guided walkthrough"
    >
      <div className="tourbar__inner">
        <ol className="tourbar__rail" aria-hidden="true">
          {Array.from({ length: total }, (_, i) => (
            <li
              key={i}
              className={`tourbar__pip ${i < step ? 'is-done' : ''} ${i === step ? 'is-now' : ''}`}
            />
          ))}
        </ol>

        <div className="tourbar__main">
          <p className="stamp-type tourbar__eyebrow">
            {part === 'more' && 'Part 2 · '}Step {step + 1} of {total} · signed in as{' '}
            {current.who}
          </p>
          <h2 className="tourbar__title">{current.title}</h2>
          {!folded && <p className="tourbar__body">{current.body}</p>}
          {!folded && current.todo && (
            <p className="tourbar__todo">
              <span className="tourbar__todomark" aria-hidden="true" />
              {current.todo}
            </p>
          )}
        </div>

        <div className="tourbar__actions">
          <button
            type="button"
            className="tourbar__fold"
            onClick={() => setFolded((f) => !f)}
            aria-expanded={!folded}
            aria-label={folded ? 'Show the explanation' : 'Hide the explanation'}
          >
            {folded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => go(step - 1)}
            disabled={step === 0 || moving}
          >
            <ArrowLeft size={14} /> Back
          </button>
          {last ? (
            part === 'main' ? (
              <>
                <button type="button" className="btn btn--ghost btn--sm" onClick={endTour}>
                  Finish
                </button>
                <button
                  type="button"
                  className="btn btn--primary btn--sm"
                  onClick={() => void startMore()}
                  disabled={moving}
                >
                  See the rest <ArrowRight size={14} />
                </button>
              </>
            ) : (
              <button type="button" className="btn btn--primary btn--sm" onClick={endTour}>
                Finish
              </button>
            )
          ) : (
            <button
              type="button"
              className="btn btn--primary btn--sm"
              onClick={() => go(step + 1)}
              disabled={moving}
            >
              {moving ? 'Opening…' : 'Next'} <ArrowRight size={14} />
            </button>
          )}
          <button type="button" className="tourbar__x" onClick={endTour} aria-label="Leave the walkthrough">
            <X size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * The way in.
 *
 * One button, on the home page and on the sign-in screen, because "show me what
 * this does" was the one request the product had no answer to. It signs the
 * visitor in as the first step's person itself — being asked to choose one of
 * five roles before you know what any of them do is the wrong first question.
 */
export function StartWalkthrough({
  className = 'btn btn--primary btn--lg',
  children = 'Take the walkthrough',
}: { className?: string; children?: React.ReactNode }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  const begin = async () => {
    setBusy(true);
    try {
      const first = TOUR[0];
      if (first.role) await signInAs(first.role);
      startTour();
      navigate(first.to);
    } catch {
      // The API is not answering. Sign-in says so in its own words.
      navigate('/login');
    } finally {
      setBusy(false);
    }
  };

  return (
    <button type="button" className={className} onClick={begin} disabled={busy}>
      {busy ? 'Starting…' : children}
      <ArrowRight size={16} />
    </button>
  );
}
