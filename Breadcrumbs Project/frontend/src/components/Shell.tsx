import {
  Binary, Boxes, CalendarCheck, FileStack, Gauge, GitBranch, KeyRound,
  LayoutGrid, LogOut, Menu, ScrollText, Search, ShieldCheck,
  Upload as UploadIcon, X,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

import type { RoleId } from '../lib/api';
import { useSession } from '../lib/session';
import { useBelow } from '../lib/useMotionPref';
import { ChainStatus } from './ChainStatus';
import { Notices } from './Notices';
import { DetailToggle, Tech } from './Tech';
import './shell.css';

// Every destination is a route, never a record. The previous version linked
// straight at `rc-001`, `vr-001` and `m-v8-rc2` — identifiers from a fixture
// file — so the navigation broke the moment the world came from the ledger
// instead. Index pages choose their own subject from what actually exists.
//
// The labels are the words the job is already done in, not the words this
// product would like to teach. Two rounds of that were needed. The first set —
// Loom floor, Bolts, The bench, The chamber, Accumulator — was a vocabulary the
// product invented outright. The second was plainer and still asked the reader
// to hold the product's own model of itself: "Check a value" is not a thing
// anybody sets out to do, "Check for gaps" names a fault rather than the task,
// and "Ledger" is the name of the machinery rather than of what is on it.
//
// So: a factory uploads documents and shares them. A buyer requests documents,
// verifies them, and checks a month is complete. Everyone can open the
// transaction history. Those are the sentences people already say.
const NAV: Record<RoleId, { to: string; label: string; icon: typeof LayoutGrid }[]> = {
  factory: [
    { to: '/factory/dashboard', label: 'Dashboard', icon: LayoutGrid },
    { to: '/factory/upload', label: 'Upload a document', icon: UploadIcon },
    { to: '/factory/records', label: 'My documents', icon: FileStack },
    // The factory is one half of every disclosure this product makes, and
    // until this existed its only control for that was a panel at the foot
    // of the activity column.
    { to: '/factory/access', label: 'Sharing & permissions', icon: KeyRound },
    // "Closed months" described the state a period ends in rather than the job
    // of putting it there, which every finance and compliance team already
    // calls closing the month.
    { to: '/periods', label: 'Month-end closing', icon: CalendarCheck },
    { to: '/ledger', label: 'Transaction history', icon: Boxes },
  ],
  buyer: [
    { to: '/buyer/portal', label: 'Request documents', icon: Search },
    // Was "Check for gaps", which names the fault rather than the check. What a
    // buyer is doing here is confirming a month is complete.
    { to: '/periods', label: 'Monthly completeness', icon: CalendarCheck },
    { to: '/verify', label: 'Verify a document', icon: ShieldCheck },
    { to: '/ledger', label: 'Transaction history', icon: Boxes },
  ],
  auditor: [
    { to: '/auditor/workspace', label: 'My audit checks', icon: Gauge },
    // An auditor reads every document on the network without asking, so it
    // needs somewhere to read them from. Without this the access was real and
    // unreachable: there was no link to any document it did not hold a grant on.
    { to: '/factory/records', label: 'All documents', icon: FileStack },
    { to: '/periods', label: 'Monthly completeness', icon: CalendarCheck },
    { to: '/verify', label: 'Verify a document', icon: ShieldCheck },
    { to: '/ledger', label: 'Transaction history', icon: Boxes },
  ],
  consortium: [
    { to: '/governance', label: 'Members & voting', icon: ScrollText },
    { to: '/model/gate', label: 'AI model approvals', icon: KeyRound },
    { to: '/model/registry', label: 'AI model history', icon: GitBranch },
    { to: '/anchor', label: 'Tamper check', icon: Binary },
    { to: '/ledger', label: 'Transaction history', icon: Boxes },
  ],
  regulator: [
    { to: '/regulator', label: 'Dashboard', icon: LayoutGrid },
    // Consortium-wide facts about the ledger, naming no document. The observer
    // may read these; it may not read a commitment, a grant or a record.
    { to: '/anchor', label: 'Tamper check', icon: Binary },
    { to: '/ledger', label: 'Transaction history', icon: Boxes },
  ],
};

const TABBABLE = 'a[href],button:not([disabled])';

/**
 * The application shell.
 *
 * Navigation is role-scoped, and the API refuses anything the navigation does
 * not offer — the two agree, which is the point.
 *
 * Below 1024px the sidebar becomes a drawer with a real top bar above it. The
 * previous arrangement — a lone burger pinned into the top-right whitespace,
 * with an unlabelled 22px ledger strip above it — was two orphans rather than a
 * navigation pattern.
 */
export function Shell() {
  const { role, signOut } = useSession();
  const { pathname } = useLocation();
  const compact = useBelow(1024);
  const [open, setOpen] = useState(false);
  const burger = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLElement>(null);

  // Widening the window past the breakpoint reveals the sidebar; the drawer
  // state must not survive that, or the scrim outlives its drawer.
  useEffect(() => {
    if (!compact) setOpen(false);
  }, [compact]);

  // Any navigation closes it. An effect on the path is more reliable than a
  // handler on each item, which misses back, forward and in-page links.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // An open drawer is modal: it traps Tab, closes on Escape, holds the page
  // behind it still, and gives focus back to the control that opened it.
  useEffect(() => {
    if (!open) return;
    const held = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    drawer.current?.querySelector<HTMLElement>(TABBABLE)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        return;
      }
      if (e.key !== 'Tab' || !drawer.current) return;
      const items = Array.from(drawer.current.querySelectorAll<HTMLElement>(TABBABLE));
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    };

    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = held;
      if (burger.current && document.body.contains(burger.current)) burger.current.focus();
    };
  }, [open]);

  if (!role) return null;

  const items = NAV[role.id];
  const modal = compact && open;

  return (
    <div className={`shellwrap shellwrap--${role.id}`}>
      {/* -- the top bar, below 1024px ----------------------------------- */}
      <header className="topbar">
        <button
          type="button"
          ref={burger}
          className="topbar__burger"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="shellnav"
          aria-label={open ? 'Close navigation' : 'Open navigation'}
        >
          {open ? <X size={19} strokeWidth={1.75} /> : <Menu size={19} strokeWidth={1.75} />}
        </button>

        <NavLink to="/" className="topbar__wordmark">Breadcrumbs</NavLink>

        <ChainStatus variant="bar" />
      </header>

      {modal && <div className="navscrim" onClick={() => setOpen(false)} />}

      <nav
        id="shellnav"
        ref={drawer}
        className={`nav grain ${open ? 'is-open' : ''}`}
        {...(modal
          ? { role: 'dialog', 'aria-modal': true, 'aria-label': 'Navigation' }
          : { 'aria-label': 'Main' })}
      >
        <div className="nav__brand">
          <NavLink to="/" className="nav__wordmark">Breadcrumbs</NavLink>
          <p className="stamp-type nav__instrument">{role.label}</p>
        </div>

        <ul className="nav__list">
          {items.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) => `nav__item ${isActive ? 'is-active' : ''}`}
              >
                <Icon size={16} strokeWidth={1.75} />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>

        <ChainStatus />
        <Notices />

        <div className="nav__foot">
          <DetailToggle dark />
          <div className="nav__who">
            <p className="nav__person">{role.person}</p>
            <p className="small nav__org">{role.org}</p>
            {/* The network identity is a string an operator needs and nobody
                else has any use for. */}
            <Tech><p className="mono nav__msp">{role.mspId}</p></Tech>
          </div>
          <button type="button" className="nav__out" onClick={signOut}>
            <LogOut size={14} strokeWidth={1.75} /> Sign out
          </button>
        </div>
      </nav>

      <main className="shellmain">
        <Outlet />
      </main>
    </div>
  );
}
