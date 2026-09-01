/**
 * Motion, in one place.
 *
 * `styles/tokens.css` owns the durations for anything a stylesheet animates.
 * A GSAP timeline cannot read a `cubic-bezier()` string out of a custom
 * property and turn it into an ease, so the two are kept deliberately in step
 * here rather than derived: change a `--m-*` token and change its twin below.
 *
 * Nothing in this application should hard-code a duration again.
 */

/** Seconds, because GSAP counts in seconds. The millisecond twins are tokens. */
export const DUR = {
  instant: 0.09, // --m-instant
  fast: 0.18, //    --m-fast
  base: 0.28, //    --m-base
  slow: 0.46, //    --m-slow
  weave: 0.7, //    --m-weave
} as const;

/** The nearest GSAP ease to each token's curve. */
export const EASE = {
  in: 'power2.in',
  out: 'power2.out',
  inOut: 'power2.inOut',
  settle: 'power3.out',
  land: 'back.out(2)',
} as const;

/** A route change, end to end. Short enough to feel like punctuation. */
export const ROUTE = 0.52;
