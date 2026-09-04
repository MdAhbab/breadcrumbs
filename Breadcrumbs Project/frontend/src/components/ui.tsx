import { Check, ChevronDown, Copy, Lock, X } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

import { shortHash } from '../lib/format';
import './ui.css';

/* ---------------------------------------------------------------- Seal ----
 * A commitment written to the chain, or the state of something on it.
 * Pressed rather than printed: a hairline ring, a tint, and letterpress type.
 * Status is never carried by colour alone — every seal has a word.
 */
export type SealTone = 'sealed' | 'pending' | 'broken' | 'inert';

const SEAL_TONE: Record<SealTone, string> = {
  sealed: 'seal--sealed',
  pending: 'seal--pending',
  broken: 'seal--broken',
  inert: 'seal--inert',
};

export function Seal({
  tone = 'sealed', children, dark = false,
}: { tone?: SealTone; children: ReactNode; dark?: boolean }) {
  return (
    <span className={`seal ${SEAL_TONE[tone]} ${dark ? 'seal--dark' : ''} stamp-type`}>
      <span className="seal__dot" aria-hidden="true" />
      {children}
    </span>
  );
}

/* ------------------------------------------------------------- Stamp ------
 * The epistemic label. How well do we know this?
 * It appears beside numbers throughout the product, because the project's
 * credibility rests on never presenting a simulated figure as a measured one.
 */
export type StampKind = 'measured' | 'simulated' | 'specified' | 'assumption';

export function Stamp({ kind, dark = false }: { kind: StampKind; dark?: boolean }) {
  return (
    <span className={`stamp stamp--${kind} ${dark ? 'stamp--dark' : ''} stamp-type`}>
      {kind}
    </span>
  );
}

/* ---------------------------------------------------------- HashChip ------
 * First twelve and last four. The truncation is visual only: the full value is
 * in the aria-label and on the clipboard.
 */
export function HashChip({ value, dark = false }: { value: string; dark?: boolean }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable; the value is still selectable */
    }
  };

  return (
    <button
      type="button"
      className={`hashchip mono ${dark ? 'hashchip--dark' : ''}`}
      onClick={copy}
      aria-label={`${copied ? 'Copied. ' : ''}Hash ${value}. Click to copy.`}
      title={value}
    >
      {copied ? 'copied' : shortHash(value)}
      {copied ? <Check size={11} /> : <Copy size={11} className="hashchip__icon" />}
    </button>
  );
}

/* ------------------------------------------------------------ Button ------ */
export function Button({
  children, variant = 'primary', size = 'md', full = false, ...rest
}: {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'onDark';
  size?: 'sm' | 'md' | 'lg';
  full?: boolean;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      className={`btn btn--${variant} btn--${size} ${full ? 'btn--full' : ''} ${rest.className ?? ''}`}
    >
      {children}
    </button>
  );
}

/* --------------------------------------------------------- Disclosure -----
 * Progressive disclosure is a rule in this product, not a preference: a buyer
 * never has to see a hash to trust an answer, and an engineer is always one
 * click from all of it.
 */
export function Disclosure({
  summary, children, open: initial = false, dark = false,
}: { summary: string; children: ReactNode; open?: boolean; dark?: boolean }) {
  const [open, setOpen] = useState(initial);
  return (
    <div className={`disclosure ${dark ? 'disclosure--dark' : ''}`}>
      <button
        type="button"
        className="disclosure__trigger"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <ChevronDown size={15} className={`disclosure__chev ${open ? 'is-open' : ''}`} />
        {summary}
      </button>
      {open && <div className="disclosure__body">{children}</div>}
    </div>
  );
}

/* ------------------------------------------------------------- Field ------ */
export function Field({
  label, hint, children, id,
}: { label: string; hint?: string; children: ReactNode; id: string }) {
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>{label}</label>
      {children}
      {hint && <p className="field__hint small">{hint}</p>}
    </div>
  );
}

/* ------------------------------------------------------- LedgerRow -------- */
export function LedgerRow({
  label, children, dark = false,
}: { label: string; children: ReactNode; dark?: boolean }) {
  return (
    <div className={`lrow ${dark ? 'lrow--dark' : ''}`}>
      <div className="lrow__label stamp-type">{label}</div>
      <div className="lrow__value">{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------ Empty ------- */
export function Empty({
  title, body, action,
}: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p className="small">{body}</p>
      {action}
    </div>
  );
}

/* ------------------------------------------------------------ Frosted -----
 * The regulator's boundary made visible.
 *
 * Most products treat permissions as absence — they hide what you cannot see.
 * Here the layout, the row count and the shape of the data stay visible while
 * the content does not, and the exact reason is stated. Absence teaches
 * nothing; a drawn boundary teaches the rule.
 */
export function Frosted({ reason, children }: { reason: string; children: ReactNode }) {
  return (
    <div className="frosted">
      <div className="frosted__content" aria-hidden="true">{children}</div>
      <div className="frosted__veil" />
      <div className="frosted__note">
        <Lock size={13} />
        <span className="small">{reason}</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ PageHead ---- */
export function PageHead({
  eyebrow, title, lede, aside,
}: { eyebrow: string; title: string; lede?: string; aside?: ReactNode }) {
  return (
    <header className="pagehead">
      <div className="pagehead__main">
        <p className="stamp-type pagehead__eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {lede && <p className="lead pagehead__lede">{lede}</p>}
      </div>
      {aside && <div className="pagehead__aside">{aside}</div>}
    </header>
  );
}

/* --------------------------------------------------------------- Modal ----
 * One dialog for the whole application.
 *
 * Rendered at the document root rather than in place: pages sit inside a
 * transform-animated stage, which is its own stacking context, and a dialog
 * trapped inside one paints beneath anything fixed no matter its z-index.
 *
 * It also does the four things a dialog must do and that hand-rolled ones
 * forget: it traps Tab, it closes on Escape, it locks the page behind it, and
 * it puts focus back where it found it.
 */
const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])', '[tabindex]:not([tabindex="-1"])',
].join(',');

/**
 * The four things a dialog must do, and that hand-rolled ones forget.
 *
 * Shared by the centred dialog and the side panel below, because they differ in
 * where they sit on the screen and in nothing else. Two copies of a focus trap
 * is two places for one of them to rot.
 */
function useDialogChrome(onClose: () => void) {
  const panel = useRef<HTMLDivElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);

  useEffect(() => {
    returnTo.current = document.activeElement as HTMLElement | null;
    const { body } = document;
    const held = body.style.overflow;
    body.style.overflow = 'hidden';

    const inside = panel.current?.querySelector<HTMLElement>(FOCUSABLE);
    (inside ?? panel.current)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab' || !panel.current) return;
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE))
        .filter((el) => el.offsetParent !== null);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    };

    window.addEventListener('keydown', onKey, true);
    return () => {
      window.removeEventListener('keydown', onKey, true);
      body.style.overflow = held;
      returnTo.current?.focus?.();
    };
  }, [onClose]);

  return panel;
}

export function Modal({
  label, onClose, className = '', children,
}: { label: string; onClose: () => void; className?: string; children: ReactNode }) {
  const panel = useDialogChrome(onClose);

  return createPortal(
    <div className="modal">
      <div className="modal__scrim" onClick={onClose} />
      <div
        ref={panel}
        className={`modal__panel grain ${className}`}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}

/* ---------------------------------------------------------------- Drawer ---
 * A form that opens from the right, over the page it belongs to.
 *
 * Closing a period, reopening one and amending one are all decisions taken
 * about a row in a list, and each was a form that unfolded *inside* its row —
 * so opening one pushed every other period down the page, and a list of thirty
 * reflowed under the reader's hands. A panel at the edge leaves the list where
 * it is, which is the thing being decided about, and gives a form with four
 * fields in it room to be four fields rather than a squeeze between two rows.
 *
 * Light rather than the dialog's indigo: these hold real forms, and every input
 * in this product is drawn for paper.
 */
export function Drawer({
  label, onClose, children,
}: { label: string; onClose: () => void; children: ReactNode }) {
  const panel = useDialogChrome(onClose);

  return createPortal(
    <div className="drawer">
      <div className="drawer__scrim" onClick={onClose} />
      <div
        ref={panel}
        className="drawer__panel"
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}

/** The side panel's header: what this is about, and the way out. */
export function DrawerHead({
  eyebrow, title, onClose,
}: { eyebrow?: string; title: string; onClose: () => void }) {
  return (
    <header className="drawer__head">
      <div>
        {eyebrow && <p className="stamp-type drawer__eyebrow">{eyebrow}</p>}
        <h3 className="drawer__title">{title}</h3>
      </div>
      <button type="button" className="drawer__x" onClick={onClose} aria-label="Close">
        <X size={16} />
      </button>
    </header>
  );
}

/** The standard dialog header: an eyebrow, a name, and the way out. */
export function ModalHead({
  eyebrow, title, onClose,
}: { eyebrow?: string; title: string; onClose: () => void }) {
  return (
    <header className="modal__head">
      <div>
        {eyebrow && <p className="stamp-type modal__eyebrow">{eyebrow}</p>}
        <h3 className="modal__title">{title}</h3>
      </div>
      <button type="button" className="modal__x" onClick={onClose} aria-label="Close">
        <X size={16} />
      </button>
    </header>
  );
}
