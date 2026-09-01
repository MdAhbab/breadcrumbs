import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';
import { ArrowRight, Check, Minus } from 'lucide-react';
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { GateSimulator } from '../components/GateSimulator';
import { Seal, Stamp } from '../components/ui';
import { LIMITATIONS, MATRIX } from '../lib/data';
import { useBelow, useReducedMotion } from '../lib/useMotionPref';
import './landing.css';

const WeaveScene = lazy(() => import('../three/WeaveScene'));
const ChainedStack = lazy(() => import('../three/ChainedStack'));

gsap.registerPlugin(ScrollTrigger);

export default function Landing() {
  const reduced = useReducedMotion();
  // Phones only. A single-draw-call instanced mesh is comfortable on a tablet;
  // it is the small, thermally-limited devices that need the still instead.
  const isPhone = useBelow(640);
  const progress = useRef(0);
  const unwind = useRef(0);
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
      unwind.current = 1;      // and the chain already paid out to its limit
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

      // The chained store unwinds across the length of the limitations list.
      ScrollTrigger.create({
        trigger: '#unwind-track',
        start: 'top 78%',
        end: 'bottom bottom',
        scrub: true,
        onUpdate: (self) => {
          unwind.current = self.progress;
        },
      });

      // Beat 2 and 3 pin their copy while the weave advances beneath. The block
      // fades in, holds, and fades back out before the top edge can cut it in
      // half — a paragraph sliced by the viewport reads as a rendering fault.
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
            <Link to="/verify/vr-001" className="lhead__link">Verify a record</Link>
            <Link to="/login" className="btn btn--onDark btn--sm">Sign in</Link>
          </nav>
        </div>
      </header>

      {/* ---------------------------------------------- beats 1-3: the weave */}
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

        {/* Beat 1 — loose threads */}
        <section className="beat beat--hero">
          <div className="shell">
            <div className="hero">
              <h1 className="hero-type">
                Prove one line.
                <br />
                Reveal nothing else.
              </h1>
              <p className="lead hero__lede">
                A permissioned ledger that makes a factory&rsquo;s own records provable —
                without publishing them, and without trusting whoever runs the server.
              </p>
              <div className="hero__actions">
                <Link to="/verify/vr-001" className="btn btn--primary btn--lg">
                  See a verification <ArrowRight size={16} />
                </Link>
                <Link to="/login" className="btn btn--onDark btn--lg">
                  Enter the portal
                </Link>
              </div>
              <div className="hero__stamp">
                <Stamp kind="specified" dark />
                <span className="small">
                  Prototype — Blockchain Olympiad 2026 finals
                </span>
              </div>
            </div>
          </div>
          <div className="scroll-cue" aria-hidden="true">
            <span />
          </div>
        </section>

        {/* Beat 2 — the weave assembles */}
        <section className="beat beat--copy">
          <div className="shell">
            <div className="beat-copy">
              <p className="stamp-type beat__num">01 — The weave</p>
              <h2>A payroll register has 1,847 rows.</h2>
              <p className="lead">
                Each row is hashed with its own salt. Pairs combine, and combine again,
                until the whole file is one number — a root, sixty-four characters long.
              </p>
              <p className="lead beat__muted">
                Only that number goes on the ledger. The file never does.
              </p>
            </div>
          </div>
        </section>

        {/* Beat 3 — pull one thread */}
        <section className="beat beat--copy beat--right">
          <div className="shell">
            <div className="beat-copy">
              <p className="stamp-type beat__num">02 — Pull one thread</p>
              <h2>One thread. Eleven hashes.</h2>
              <p className="lead">
                To prove one worker&rsquo;s pay, the factory reveals that row, its salt,
                and the eleven sibling hashes on its path to the root. A buyer recomputes
                the root and compares.
              </p>
              <p className="lead beat__accent">
                The buyer learned one number. The other 1,846 rows never left the building.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* ------------------------------------------------- beat 4: the loom */}
      <DecisionLoom />

      {/* -------------------------------------------------- beat 5: the gate */}
      <section className="beat-block beat-block--dark grain warp">
        <div className="shell">
          <div className="section-head" data-rise>
            <div>
              <p className="stamp-type section-head__eyebrow">03 — The Continuity Gate</p>
              <h2 className="on-dark">A model that improves can still be getting worse.</h2>
              <p className="lead on-dark-muted">
                A new detector is better at this month&rsquo;s problem and quietly worse at
                last year&rsquo;s. Forgetting does not make an update look bad — on the data
                a review committee is looking at, it looks excellent. So the rule moves
                into a contract that looks backwards.
              </p>
            </div>
          </div>
          <GateSimulator />
        </div>
      </section>

      {/* ------------------------------------------------ beat 6: the matrix */}
      <section className="beat-block">
        <div className="shell">
          <div className="section-head" data-rise>
            <div>
              <p className="stamp-type section-head__eyebrow">04 — Where we sit</p>
              <h2>We lose most of these columns.</h2>
              <p className="lead section-head__lede">
                Notarisation already makes documents tamper-evident. LiFeChain already puts
                federated lifelong learning on a chain. We only claim the last column.
              </p>
            </div>
          </div>

          <div className="matrix-wrap scroll-x">
            <table className="matrix">
              <thead>
                <tr>
                  <th scope="col">System</th>
                  {MATRIX.columns.map((c, i) => (
                    <th key={c} scope="col" className={i === MATRIX.columns.length - 1 ? 'is-ours' : ''}>
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {MATRIX.rows.map((row) => {
                  const ours = row.name === 'Breadcrumbs';
                  return (
                    <tr key={row.name} className={ours ? 'is-ours' : ''}>
                      <th scope="row">{row.name}</th>
                      {row.cells.map((on, i) => (
                        <td key={i} className={i === row.cells.length - 1 && on ? 'is-key' : ''}>
                          {on ? <Check size={15} /> : <Minus size={13} className="dash" />}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* -------------------------------------------- beat 7: the limitations */}
      <section className="beat-block beat-block--vat grain" id="unwind-track">
        <div className="unwind-stage">
          {/* Pinned, so the store stays in view while the admissions scroll past
              it — the wrap loosening as you read is the whole device. */}
          <div className="unwind-pin">
            {showCanvas ? (
              <Suspense fallback={<ChainedStill />}>
                <ChainedStack progress={unwind} />
              </Suspense>
            ) : (
              <ChainedStill />
            )}
            <div className="unwind-veil" />
          </div>
        </div>

        <div className="shell unwind-copy">
          <div className="section-head" data-rise>
            <div>
              <p className="stamp-type section-head__eyebrow">05 — Disclosure</p>
              <h2 className="on-dark">What we cannot do yet.</h2>
              <p className="lead on-dark-muted">
                One tier of the store for each thing still holding us. The wrap loosens as
                you read — and does not come off, because these are not solved.
              </p>
            </div>
          </div>

          <ol className="limits" data-rise>
            {LIMITATIONS.map((l, i) => (
              <li key={i} className="limit">
                <span className="limit__n mono">{String(i + 1).padStart(2, '0')}</span>
                <p>{l}</p>
              </li>
            ))}
          </ol>

          <p className="small unwind-note">
            Every one of these is in the report, in the same words.
          </p>
        </div>
      </section>

      {/* ------------------------------------------------------ beat 8: close */}
      <section className="beat-block beat-block--close grain warp">
        <div className="shell close">
          <h2 className="hero-type close__line">
            Prove one line.
            <br />
            Reveal nothing else.
          </h2>
          <div className="close__actions">
            <Link to="/verify/vr-001" className="btn btn--primary btn--lg">
              Verify a record
            </Link>
            <Link to="/login" className="btn btn--onDark btn--lg">
              Sign in
            </Link>
          </div>
          <p className="small close__meta">
            Team CookieMonsters · United International University · 2026
          </p>
        </div>
      </section>
    </div>
  );
}

/* ------------------------------------------------------- the chained still --
 * The phone and reduced-motion rendering of the constrained store: the same
 * platters, the same wrap, drawn once and not moving. The links overlap along
 * their turn for the same reason they do in the scene — a row of separated
 * ovals reads as beads, and only an overlapping one reads as a chain.
 */
function ChainedStill() {
  const platters = Array.from({ length: 9 }, (_, i) => ({ cy: 40 + i * 20, freed: i <= 4 }));
  const turns = [148, 168, 188, 208];
  const perTurn = 38;

  return (
    <svg
      className="chained-still"
      viewBox="0 0 200 252"
      aria-hidden="true"
      preserveAspectRatio="xMidYMid meet"
    >
      {platters.map(({ cy, freed }) => (
        <g key={cy}>
          <path className="cs-body" d={`M52 ${cy} v9 a48 12 0 0 0 96 0 v-9`} />
          <ellipse className="cs-body" cx="100" cy={cy} rx="48" ry="12" />
          <ellipse
            className={`cs-rim ${freed ? 'is-freed' : ''}`}
            cx="100"
            cy={cy + 9}
            rx="48"
            ry="12"
          />
        </g>
      ))}

      {turns.map((cy) =>
        Array.from({ length: perTurn }, (_, j) => {
          const a = (j / perTurn) * Math.PI * 2;
          const front = Math.sin(a) > 0;
          return (
            <ellipse
              key={`${cy}-${j}`}
              className="cs-link"
              cx={100 + Math.cos(a) * 52}
              cy={cy + Math.sin(a) * 13}
              rx={j % 2 ? 2.9 : 4.5}
              ry={j % 2 ? 4.5 : 2.9}
              opacity={front ? 0.95 : 0.34}
            />
          );
        }),
      )}

      {/* what has come off, heaped at the foot */}
      {Array.from({ length: 30 }, (_, j) => {
        const s = j / 29;
        const a = s * 13.5;
        const r = 5 + s * 21;
        return (
          <ellipse
            key={`heap-${j}`}
            className="cs-link is-slack"
            cx={150 + Math.cos(a) * r}
            cy={228 + Math.sin(a) * r * 0.3}
            rx={j % 2 ? 2.6 : 4.1}
            ry={j % 2 ? 4.1 : 2.6}
          />
        );
      })}
    </svg>
  );
}

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

/* ------------------------------------------------------ the Decision Loom --
 * Three shuttles in a track. All three conditions must hold for a blockchain to
 * be the right answer — the Wüst–Gervais test. The visitor proves it to
 * themselves, which is far more persuasive than being told.
 */
function DecisionLoom() {
  const [state, setState] = useState([true, true, true]);
  const all = state.every(Boolean);

  const CONDITIONS = [
    'Multiple parties write to the same record',
    'No single trusted custodian',
    'The parties do not fully trust each other',
  ];

  const firstOff = state.findIndex((s) => !s);

  return (
    <section className="beat-block beat-block--cotton">
      <div className="shell">
        <div className="section-head" data-rise>
          <div>
            <p className="stamp-type section-head__eyebrow">02b — Why a blockchain</p>
            <h2>Turn one off and the answer changes.</h2>
            <p className="lead section-head__lede">
              Three conditions decide whether a distributed ledger is justified at all.
              All three hold in this industry — which is the only reason we claim it.
            </p>
          </div>
        </div>

        <div className="loom">
          <div className="loom__shuttles">
            {CONDITIONS.map((c, i) => (
              <button
                key={c}
                type="button"
                className={`shuttle ${state[i] ? 'is-on' : ''}`}
                onClick={() => setState((s) => s.map((v, j) => (j === i ? !v : v)))}
                aria-pressed={state[i]}
              >
                <span className="shuttle__track">
                  <span className="shuttle__knob" />
                </span>
                <span className="shuttle__label">{c}</span>
              </button>
            ))}
          </div>

          <div className={`verdict ${all ? 'is-yes' : 'is-no'}`}>
            <Seal tone={all ? 'sealed' : 'inert'}>
              {all ? 'Justified' : 'Not justified'}
            </Seal>
            <h3 className="verdict__line">
              {all ? 'A blockchain is justified.' : 'Use a database.'}
            </h3>
            <p className="small verdict__why">
              {all
                ? 'Multiple writers, no candidate custodian, and mutual distrust. All three hold, so the ledger earns its place.'
                : `Without “${CONDITIONS[firstOff].toLowerCase()}”, an ordinary database with good access logs does the same job more cheaply.`}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
