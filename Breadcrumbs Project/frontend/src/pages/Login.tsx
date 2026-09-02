import { ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Failed, Result } from '../components/states';
import { ApiError, type RoleOption } from '../lib/api';
import { api } from '../lib/api';
import { INSTRUMENT, useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import './login.css';

/**
 * Choosing who you are.
 *
 * The roles are the API's, not a list kept here — `/api/auth/roles` is the same
 * table the capability checks are enforced against, so a role that exists on
 * this screen is a role the ledger will actually issue a certificate for.
 *
 * Not a stack of identical rows: each role is a different job, and the card
 * shows the instrument it opens onto.
 */
export default function Login() {
  const [picked, setPicked] = useState<RoleOption | null>(null);
  const [entering, setEntering] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const { signIn } = useSession();
  const navigate = useNavigate();
  const roles = useApi(() => api.roles(), []);

  const enter = async () => {
    if (!picked) return;
    setEntering(true);
    setFailure(null);
    try {
      navigate(await signIn(picked), { replace: true });
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'sign-in failed'));
      setEntering(false);
    }
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
          ledger. Authentication is simulated — no credential is asked for, and the
          API accepts any six-digit code. What is not simulated is everything after:
          each role receives a real token, and every rule below is enforced against
          it by the contract rather than by hiding a button.
        </p>

        <Result query={roles} pendingLabel="Asking the API which roles exist">
          {(options) => (
            <ul className="roles">
              {options.map((r, i) => (
                <li key={r.role}>
                  <button
                    type="button"
                    className={`role ${picked?.role === r.role ? 'is-picked' : ''}`}
                    onClick={() => setPicked(r)}
                    aria-pressed={picked?.role === r.role}
                    style={{ animationDelay: `${i * 55}ms` }}
                  >
                    <span className="role__n mono">{String(i + 1).padStart(2, '0')}</span>
                    <span className="role__body">
                      <span className="role__label">{r.label}</span>
                      <span className="role__org">{r.org}</span>
                      <span className="role__summary">{r.summary}</span>
                    </span>
                    <span className="role__instrument stamp-type">{INSTRUMENT[r.role]}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Result>

        {failure && <div className="login__failure"><Failed error={failure} /></div>}

        <div className="login__actions">
          <button
            type="button"
            className="btn btn--primary btn--lg"
            onClick={enter}
            disabled={!picked || entering}
          >
            {entering ? 'Signing in…' : `Enter${picked ? ` as ${picked.person}` : ''}`}
            <ArrowRight size={16} />
          </button>
          <Link to="/verify" className="login__nolink">
            Verify a record without signing in
          </Link>
        </div>

        <p className="small login__foot">
          Team CookieMonsters · United International University
        </p>
      </div>
    </div>
  );
}
