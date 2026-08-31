/*
 * The application shell: a fixed indigo sidebar and a loom-coloured content
 * area, per designs_instructions.md §6.
 *
 * Navigation is role-scoped. A regulator does not see a link to a factory
 * record, and the API refuses one anyway — the two agree, which is the point.
 */

import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { clearSession, loadSession, type Role } from '../lib/api';

const NAV: Record<Role, { to: string; label: string }[]> = {
  factory: [
    { to: '/factory/dashboard', label: 'Dashboard' },
    { to: '/factory/upload', label: 'Upload record' },
    { to: '/factory/records', label: 'Records' },
    { to: '/factory/access', label: 'Access grants' },
  ],
  buyer: [
    { to: '/buyer/portal', label: 'Request portal' },
    { to: '/verify', label: 'Verify a record' },
  ],
  auditor: [
    { to: '/auditor/workspace', label: 'Batch workspace' },
    { to: '/verify', label: 'Verify a record' },
  ],
  consortium: [
    { to: '/governance', label: 'Governance' },
    { to: '/ops/sla', label: 'SLA & operations' },
    { to: '/model/registry', label: 'Model registry' },
    { to: '/model/rounds', label: 'Training rounds' },
    { to: '/model/benchmarks', label: 'Benchmarks' },
    { to: '/ledger', label: 'Ledger explorer' },
  ],
  regulator: [
    { to: '/regulator', label: 'Observer view' },
    { to: '/ops/sla', label: 'SLA dashboard' },
    { to: '/ledger', label: 'Ledger explorer' },
  ],
};

export function Shell() {
  const session = loadSession();
  const navigate = useNavigate();
  if (!session) return null;

  const signOut = () => {
    clearSession();
    navigate('/login', { replace: true });
  };

  return (
    <div style={{ display: 'flex', minHeight: '100%' }}>
      <nav
        style={{
          width: 'var(--sidebar-width)',
          flexShrink: 0,
          background: 'var(--indigo-900)',
          color: 'var(--loom-50)',
          display: 'flex',
          flexDirection: 'column',
          padding: 'var(--space-lg) 0',
        }}
      >
        <div style={{ padding: '0 var(--space-lg) var(--space-xl)' }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 600 }}>
            Breadcrumbs
          </div>
          <div className="mono-label" style={{ color: 'var(--thread)', marginTop: 2 }}>
            Ledger Portal
          </div>
        </div>

        <div style={{ flex: 1 }}>
          {NAV[session.role].map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              style={({ isActive }) => ({
                display: 'block',
                padding: 'var(--space-sm) var(--space-lg)',
                color: isActive ? 'var(--brass)' : 'var(--loom-100)',
                background: isActive ? 'var(--brass-12)' : 'transparent',
                borderLeft: `2px solid ${isActive ? 'var(--brass)' : 'transparent'}`,
                textDecoration: 'none',
                fontWeight: isActive ? 500 : 400,
                transition: 'background var(--motion-instant)',
              })}
            >
              {item.label}
            </NavLink>
          ))}
        </div>

        <div style={{ padding: 'var(--space-lg) var(--space-lg) 0', borderTop: '1px solid var(--indigo-700)' }}>
          <div style={{ fontWeight: 500 }}>{session.person}</div>
          <div style={{ color: 'var(--thread)', fontSize: 13 }}>{session.org}</div>
          <button
            onClick={signOut}
            style={{
              marginTop: 'var(--space-md)',
              background: 'none',
              border: 'none',
              color: 'var(--loom-100)',
              cursor: 'pointer',
              padding: 0,
              font: 'inherit',
            }}
          >
            Sign out
          </button>
        </div>
      </nav>

      <main style={{ flex: 1, minWidth: 0 }}>
        <Outlet />
      </main>
    </div>
  );
}
