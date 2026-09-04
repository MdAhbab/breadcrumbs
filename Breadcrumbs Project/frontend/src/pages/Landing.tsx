import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { StartWalkthrough } from '../components/TourBar';
import { useBelow, useReducedMotion } from '../lib/useMotionPref';
import './landing.css';

const WeaveScene = lazy(() => import('../three/WeaveScene'));

gsap.registerPlugin(ScrollTrigger);

/**
 * The front door.
 *
 * This page had become a summary of the report rather than an introduction to
 * the product. It carried a competitor matrix, a list of the system's own
 * unsolved limitations, the corpus seed and manifest digest, a toggle
 * demonstrating the Wüst–Gervais test for whether a blockchain is justified,
 * and a simulator of the machine-learning gate. Every one of those is true and
 * worth publishing, and none of them answers the question somebody arriving
 * here actually has, which is: what is this, and what would I do with it?
 *
 * So the page is now an introduction. What the problem is, what Breadcrumbs
 * does about it, the four steps of using it, and who each step belongs to. A
 * reader who has never heard of a Merkle tree should be able to finish it and
 * explain the product to somebody else. The engineering detail did not go
 * anywhere — it is in the report, in the walkthrough, and on the screens
 * themselves, where somebody who wants it will be looking for it.
 */
export default function Landing() {
  const reduced = useReducedMotion();
  // Phones only. A single-draw-call instanced mesh is comfortable on a tablet;
  // it is the small, thermally-limited devices that need the still instead.
  const isPhone = useBelow(640);
  const progress = useRef(0);
  const root = useRef<HTMLDivElement>(null);
  const [showCanvas, setShowCanvas] = useState(false);
  const [stuck, setStuck] = useState(false);

  // The header is transparent over the hero and takes a ground once the reader
  // has left it, so it never competes with the opening statement.
  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 48);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // The hero text must paint before anything expensive starts. The canvas is
  // lazy-loaded and only mounted once the first frame is on screen; a 3D hero
  // that blocks reading is worse than no 3D hero.
  useEffect(() => {
    if (reduced || isPhone) return;
    const id = window.requestAnimationFrame(() =>
      window.setTimeout(() => setShowCanvas(true), 120),
    );
    return () => window.cancelAnimationFrame(id);
  }, [reduced, isPhone]);

  useEffect(() => {
    if (reduced) {
      progress.current = 0.75; // render the woven, traced state immediately
      return;
    }

    const lenis = new Lenis({ duration: 1.05, smoothWheel: true });
    const raf = (time: number) => {
      lenis.raf(time);
      requestAnimationFrame(raf);
    };
    const handle = requestAnimationFrame(raf);
    lenis.on('scroll', ScrollTrigger.update);

    const ctx = gsap.context(() => {
      // One scrubbed timeline drives the whole weave. The user owns the
      // timeline: scrolling back unweaves the cloth.
      ScrollTrigger.create({
        trigger: '#weave-track',
        start: 'top top',
        end: 'bottom bottom',
        scrub: true,
        onUpdate: (self) => {
          progress.current = self.progress;
        },
      });

      // The two copy beats hold while the weave advances beneath. Each fades
      // in, holds, and fades out before the top edge can cut it in half — a
      // paragraph sliced by the viewport reads as a rendering fault.
      gsap.utils.toArray<HTMLElement>('.beat-copy').forEach((el) => {
        gsap
          .timeline({
            scrollTrigger: { trigger: el, start: 'top 88%', end: 'bottom 14%', scrub: true },
          })
          .fromTo(el, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 1, ease: 'power2.out' })
          .to(el, { opacity: 1, duration: 1.7 })
          .to(el, { opacity: 0, y: -16, duration: 0.9, ease: 'power2.in' });
      });

      // Everything below the weave rises in on entry, staggered by 40ms.
      gsap.utils.toArray<HTMLElement>('[data-rise]').forEach((el) => {
        gsap.from(el.children, {
          opacity: 0,
          y: 20,
          duration: 0.55,
          stagger: 0.04,
          ease: 'power2.out',
          scrollTrigger: { trigger: el, start: 'top 78%' },
        });
      });
    }, root);

    return () => {
      ctx.revert();
      cancelAnimationFrame(handle);
      lenis.destroy();
    };
  }, [reduced]);

  return (
    <div className="landing grain" ref={root}>
      <header className={`lhead ${stuck ? 'is-stuck' : ''}`}>
        <div className="shell lhead__in">
          <Link to="/" className="lhead__mark">Breadcrumbs</Link>
          <nav className="lhead__nav" aria-label="Primary">
            <Link to="/verify/vr-001" className="lhead__link">See a real check</Link>
            <Link to="/login" className="btn btn--onDark btn--sm">Sign in</Link>
          </nav>
        </div>
      </header>

      {/* ------------------------------------------------- the opening beats */}
      <div id="weave-track" className="weave-track">
        <div className="weave-stage warp">
          {showCanvas ? (
            <Suspense fallback={<WovenStill />}>
              <WeaveScene progress={progress} />
            </Suspense>
          ) : (
            <WovenStill />
          )}
          <div className="weave-vignette" />
        </div>

        {/* The opening claim, in the words the product would use to a stranger */}
        <section className="beat beat--hero">
          <div className="shell">
            <div className="hero">
              <h1 className="hero-type">
                Prove one line.
                <br />
                Reveal nothing else.
              </h1>
              <p className="lead hero__lede">
                Breadcrumbs lets a factory show that its own paperwork is genuine —
                a wage sheet, a safety inspection, a chemical inventory — without
                handing the file over, and without anyone having to take its word,
                or ours, for any of it.
              </p>
              {/* The walkthrough is first, and it is the primary button. A
                  visitor who has not seen the product cannot pick one of five
                  roles, and "see a verification" drops them at the end of a
                  story whose beginning they have not been told. */}
              <div className="hero__actions">
                <StartWalkthrough className="btn btn--primary btn--lg">
                  Show me how it works
                </StartWalkthrough>
                <Link to="/login" className="btn btn--onDark btn--lg">
                  Sign in
                </Link>
              </div>
            </div>
          </div>
          <div className="scroll-cue" aria-hidden="true">
            <span />
          </div>
        </section>

        {/* The problem, before any of the machinery */}
        <section className="beat beat--copy">
          <div className="shell">
            <div className="beat-copy">
              <p className="stamp-type beat__num">The problem</p>
              <h2>Nobody believes the paperwork.</h2>
              <p className="lead">
                A clothing brand cannot tell whether a supplier&rsquo;s wage sheet is the
                real one, so it sends auditors. The factory pays for audit after audit,
                shows the same documents again, and the documents can still be edited
                the day after anyone looks at them.
              </p>
              <p className="lead beat__muted">
                And the fraud that actually happens is not a forged wage sheet. It is a
                second one, and a decision about which to show.
              </p>
            </div>
          </div>
        </section>

        {/* The answer, in one plain paragraph */}
        <section className="beat beat--copy beat--right">
          <div className="shell">
            <div className="beat-copy">
              <p className="stamp-type beat__num">The idea</p>
              <h2>Publish a fingerprint. Keep the file.</h2>
              <p className="lead">
                When a factory files a document here, the file stays in the factory. What
                goes onto the shared record is a fingerprint of it — a short code that
                could not be worked back into the document, and could not be produced
                again by a different one.
              </p>
              <p className="lead beat__accent">
                Later the factory can release a single figure out of that file and prove
                it belongs to the original. One line goes across. Everything else stays
                where it was.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* ---------------------------------------------------- how it works */}
      <section className="beat-block beat-block--cotton">
        <div className="shell">
          <div className="section-head" data-rise>
            <div>
              <p className="stamp-type section-head__eyebrow">How it works</p>
              <h2>Four steps, and the whole product is in them.</h2>
              <p className="lead section-head__lede">
                Nothing is automatic and nothing is hidden. Each step is somebody
                deciding something, and each one leaves a record the other side can
                check for itself.
              </p>
            </div>
          </div>

          <ol className="steps" data-rise>
            {STEPS.map((s, i) => (
              <li key={s.title} className="step">
                <span className="step__n mono">{String(i + 1).padStart(2, '0')}</span>
                <p className="stamp-type step__who">{s.who}</p>
                <h3 className="step__h">{s.title}</h3>
                <p className="step__p">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ---------------------------------------------- the part that is new */}
      <section className="beat-block beat-block--dark grain warp">
        <div className="shell">
          <div className="section-head" data-rise>
            <div>
              <p className="stamp-type section-head__eyebrow">Why it is different</p>
              <h2 className="on-dark">Being real is not the same as being all of it.</h2>
              <p className="lead on-dark-muted">
                Plenty of systems can tell you a document is genuine. Hand a brand four
                wage sheets and every one of them checks out — and the fifth, the bad
                week, was simply never mentioned. A check that only looks at what it is
                given can never notice what it was not.
              </p>
            </div>
          </div>

          <div className="claims" data-rise>
            <div className="claim">
              <h3 className="claim__h">A month gets closed</h3>
              <p className="claim__p">
                When a factory finishes a month, it closes it: the shared record fixes
                how many documents that month contained, before anybody asks to see any
                of them.
              </p>
            </div>
            <div className="claim">
              <h3 className="claim__h">The arithmetic does the accusing</h3>
              <p className="claim__p">
                A buyer shown four documents for a month closed at five does not need to
                suspect anything. The numbers do not add up, and that is a fact rather
                than a complaint.
              </p>
            </div>
            <div className="claim">
              <h3 className="claim__h">Nobody owns the record</h3>
              <p className="claim__p">
                Factories, brands, auditors and the trade body all hold the same copy.
                Adding to it takes agreement, and nothing already in it can be edited by
                anybody — including us.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* -------------------------------------------------------- who it is for */}
      <section className="beat-block">
        <div className="shell">
          <div className="section-head" data-rise>
            <div>
              <p className="stamp-type section-head__eyebrow">Who uses it</p>
              <h2>Five people, one record between them.</h2>
              <p className="lead section-head__lede">
                Signing in as any of them takes one press, and each sees only what that
                job is allowed to see. The walkthrough visits all five in order.
              </p>
            </div>
          </div>

          <ul className="whouses" data-rise>
            {ROLES.map((r) => (
              <li key={r.who} className="whouses__row">
                <p className="whouses__who">{r.who}</p>
                <p className="whouses__what">{r.what}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ------------------------------------------------------------- close */}
      <section className="beat-block beat-block--close grain warp">
        <div className="shell close">
          <h2 className="hero-type close__line">
            Prove one line.
            <br />
            Reveal nothing else.
          </h2>
          <div className="close__actions">
            <StartWalkthrough className="btn btn--primary btn--lg">
              Show me how it works
            </StartWalkthrough>
            <Link to="/login" className="btn btn--onDark btn--lg">
              Sign in
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

/**
 * The workflow, as four sentences.
 *
 * Written for somebody who has never used the product and does not yet know
 * that it has five roles: each step says whose step it is, in the words that
 * job goes by, before it says what happens.
 */
const STEPS: { who: string; title: string; body: string }[] = [
  {
    who: 'The factory',
    title: 'Files a document',
    body:
      'A wage sheet or an inspection is uploaded. The file stays in the factory; only '
      + 'its fingerprint goes onto the shared record, along with what kind of document '
      + 'it is and which month it covers.',
  },
  {
    who: 'A brand or buyer',
    title: 'Asks for one figure',
    body:
      'Not the file, and not a copy of it. One column of one kind of document for one '
      + 'month, with a reason attached. The request goes to the factory, which is free '
      + 'to say no.',
  },
  {
    who: 'The factory',
    title: 'Decides, and can change its mind',
    body:
      'Saying yes releases that one column of one document, until a date it sets. It '
      + 'can be withdrawn later, and withdrawing it is recorded with the reason, under '
      + 'the name of whoever did it.',
  },
  {
    who: 'The buyer, or an auditor',
    title: 'Checks it, and checks nothing is missing',
    body:
      'The released figure is checked against the fingerprint the factory published '
      + 'months earlier. Then the month itself is checked: closed at five documents, '
      + 'shown four, and the shortfall is arithmetic rather than suspicion.',
  },
];

const ROLES: { who: string; what: string }[] = [
  {
    who: 'Factory',
    what:
      'Files documents, decides who may see which column of them, closes each month, '
      + 'and can see every use anybody has made of what it released.',
  },
  {
    who: 'Brand or buyer',
    what:
      'Asks for the figures it needs, reads what it was given, checks each one against '
      + 'the record, and confirms a month is complete.',
  },
  {
    who: 'Auditor',
    what:
      'Reads every document on the network without asking — an audit where the audited '
      + 'party picks what may be looked at is not an audit — and signs off on what it '
      + 'examined. Names of workers stay closed to it, as to everyone.',
  },
  {
    who: 'Trade body',
    what:
      'Admits and suspends members by vote, and approves the shared fraud detector '
      + 'before any new version of it can be used.',
  },
  {
    who: 'Regulator',
    what:
      'Watches. Sees governance and totals, no factory document at all, and can still '
      + 'check that nothing in the record has been altered.',
  },
];

/* -------------------------------------------------------------- the still --
 * What a phone gets, and what anyone with reduced motion preferences gets: the
 * same cloth, composed and still. Pure SVG, a few kilobytes, no canvas.
 */
function WovenStill() {
  const N = 26;
  return (
    <svg className="woven-still" viewBox="0 0 200 200" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
      <g className="ws-warp" strokeWidth="0.55">
        {Array.from({ length: N }, (_, i) => (
          <line key={`w${i}`} x1={12 + i * 7} y1="14" x2={12 + i * 7} y2="186" opacity={0.28 + (i % 3) * 0.12} />
        ))}
        {Array.from({ length: N }, (_, i) => (
          <line key={`f${i}`} x1="14" y1={12 + i * 7} x2="186" y2={12 + i * 7} opacity={0.2 + (i % 4) * 0.1} />
        ))}
      </g>
      {/* the traced thread and its proof path */}
      <line x1="14" y1="96" x2="186" y2="96" className="ws-trace" strokeWidth="1.15" />
      {[47, 61, 89, 117, 145].map((x) => (
        <circle key={x} cx={x} cy="96" r="1.6" className="ws-node" />
      ))}
    </svg>
  );
}
