/** Presentation helpers. Nothing here touches domain logic. */

/** Basis points to a display percentage: 7790 → "77.9". */
export const bp = (v: number, digits = 1) => (v / 100).toFixed(digits);

/** Signed change in points: -1805 → "−18.1". Uses a real minus sign. */
export const bpDelta = (v: number, digits = 1) =>
  `${v < 0 ? '−' : '+'}${Math.abs(v / 100).toFixed(digits)}`;

/** First 12 and last 4 of a hash. Truncation is visual only. */
export const shortHash = (h: string) =>
  h.length <= 18 ? h : `${h.slice(0, 12)}…${h.slice(-4)}`;

export const commas = (n: number) => n.toLocaleString('en-GB');

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-08-05T09:14:00Z" → "5 Aug 2026". */
export function longDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** "2026-08-05T09:14:00Z" → "5 Aug 2026 · 15:14 GMT+6" (site local time). */
export function dateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const local = new Date(d.getTime() + 6 * 3600 * 1000);
  const hh = String(local.getUTCHours()).padStart(2, '0');
  const mm = String(local.getUTCMinutes()).padStart(2, '0');
  return `${longDate(iso)} · ${hh}:${mm} GMT+6`;
}

/** "2026-07" → "July 2026"; passes through quarters like "2026-Q2". */
export function period(p: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(p);
  if (!m) return p.replace('-', ' ');
  const FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
    'August', 'September', 'October', 'November', 'December'];
  return `${FULL[Number(m[2]) - 1]} ${m[1]}`;
}
