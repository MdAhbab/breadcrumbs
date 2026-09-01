import { ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';

import { ROLES, type RoleId } from '../lib/data';
import { useSession } from '../lib/session';
import './login.css';

/**
 * Choosing who you are.
 *
 * Not a stack of identical rows: each role is a different job, and the card
 * shows the instrument it opens onto. The one you hover reveals its grammar,
 * so the choice is informative rather than arbitrary.
 */
export default function Login() {
  const [picked, setPicked] = useState<RoleId | null>(null);
  const { signIn } = useSession();
  const navigate = useNavigate();

  const enter = () => {
    if (!picked) return;
    signIn(picked);
    navigate(ROLES.find((r) => r.id === picked)!.landing, { replace: true });
  };

  return (
    <div className="login grain warp">
      <div className="login__inner">
        <header className="login__head">
          <Link to="/" className="login__wordmark">Breadcrumbs</Link>
          <p className="stamp-type login__sub">Permissioned ledger · verifiable factory records</p>
        </header>

        <h1 className="login__title">Who is at the loom?</h1>
        <p className="lead login__lede">
          Five roles, five instruments. Each opens onto a different view of the same
          ledger. This demonstration uses simulated authentication.
        </p>

        <ul className="roles">
          {ROLES.map((r, i) => (
            <li key={r.id}>
              <button
                type="button"
                className={`role ${picked === r.id ? 'is-picked' : ''}`}
                onClick={() => setPicked(r.id)}
                aria-pressed={picked === r.id}
                style={{ animationDelay: `${i * 55}ms` }}
              >
                <span className="role__n mono">{String(i + 1).padStart(2, '0')}</span>
                <span className="role__body">
                  <span className="role__label">{r.label}</span>
                  <span className="role__org">{r.org}</span>
                  <span className="role__summary">{r.summary}</span>
                </span>
                <span className="role__instrument stamp-type">{r.instrument}</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="login__actions">
          <button
            type="button"
            className="btn btn--primary btn--lg"
            onClick={enter}
            disabled={!picked}
          >
            Enter {picked ? `as ${ROLES.find((r) => r.id === picked)!.person}` : ''}
            <ArrowRight size={16} />
          </button>
          <Link to="/verify/vr-001" className="login__nolink">
            Verify a record without signing in
          </Link>
        </div>

        <p className="small login__foot">
          Team CookieMonsters · United International University · 2026
        </p>
      </div>
    </div>
  );
}
