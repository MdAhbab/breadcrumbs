import { taskLabel } from './api';

/**
 * The contract's own words for a decision, said in plain ones.
 *
 * The reason string is written into the ledger by the chaincode, so it is a
 * record and not a label: it must not be reworded at the source, and the
 * technical view still shows it exactly as stored. But "accuracy on
 * wage_register_inconsistency fell by 3593 bp, tolerance is 500 bp" is the
 * headline of the most important screen in the product, and basis points are
 * not a unit anybody outside finance reads without converting.
 *
 * Anything that does not match a known pattern is returned untouched, which is
 * the right failure: an unrecognised reason should be shown as written rather
 * than mangled into something that reads well and means something else.
 */

/** 3593 → "35.9%". Basis points are hundredths of a percent. */
const pct = (bp: string) => `${(Number(bp) / 100).toFixed(1)}%`;

const RULES: [RegExp, (m: RegExpMatchArray) => string][] = [
  [
    /^accuracy on (\S+) fell by (\d+) bp, tolerance is (\d+) bp$/,
    (m) => `It got ${pct(m[2])} worse at ${taskLabel(m[1]).toLowerCase()}. `
      + `The agreed limit is ${pct(m[3])}.`,
  ],
  [
    /^gained (\d+) bp on (\S+), lost no more than (\d+) bp on any earlier task this round and no more than (\d+) bp against its best$/,
    (m) => `It improved by ${pct(m[1])} at ${taskLabel(m[2]).toLowerCase()}, `
      + `and got no more than ${pct(m[3])} worse at anything it already knew.`,
  ],
  [
    /^endorsers disagree on (\S+) by (\d+) bp, tolerance is (\d+) bp$/,
    (m) => `The organisations that tested it disagreed by ${pct(m[2])} on `
      + `${taskLabel(m[1]).toLowerCase()}, and only ${pct(m[3])} is allowed.`,
  ],
  [
    /^accuracy on (\S+) is (\d+) bp below its best of (\d+) bp, cumulative tolerance is (\d+) bp$/,
    (m) => `It is now ${pct(m[2])} below the best it ever managed at `
      + `${taskLabel(m[1]).toLowerCase()}. The most it is allowed to slip in total `
      + `is ${pct(m[4])}.`,
  ],
];

export function plainReason(reason: string): string {
  for (const [pattern, say] of RULES) {
    const match = reason.match(pattern);
    if (match) return say(match);
  }
  // Nothing matched. Say it as stored rather than guess.
  return reason;
}
