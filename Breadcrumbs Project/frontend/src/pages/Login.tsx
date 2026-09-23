import { ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Failed, Result } from '../components/states';
import { StartWalkthrough } from '../components/TourBar';
import { ApiError, type RoleOption } from '../lib/api';
import { api } from '../lib/api';
import { useSession } from '../lib/session';
import { TOUR } from '../lib/tour';
import { useApi } from '../lib/useApi';
import './login.css';

/**
 * Choosing who you are.
 *
 * The roles are the API's, not a list kept here — `/api/auth/roles` is the same
 * table the capability checks are enforced against, so a role that exists on
 * this screen is a role the ledger will actually issue a certificate for.
 *
 * Each card now says what that person can do, in a verb. The previous version
 * ended each row with an invented name for the screen behind it — the Loom
 * Floor, the Lightbox, the Bench — which asked the visitor to learn five words
 * before they could make the first choice the product requires of them.
 *
 * And the first choice is no longer required at all: the walkthrough picks for
 * you, because "which of these five am I?" is an unfair question to put to
 * someone who has not yet seen the thing work.
 */
export default function Login() {
  // One press signs in. The earlier pick-then-Enter pair put the Enter button
  // below the fold on a laptop screen, so choosing a role appeared to do
  // nothing until the visitor thought to scroll.
  const [entering, setEntering] = useState<RoleOption['role'] | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);
  const { signIn } = useSession();
  const navigate = useNavigate();
  const roles = useApi(() => api.roles(), []);

  const enter = async (picked: RoleOption) => {
    if (entering) return;
    setEntering(picked.role);
    setFailure(null);
    try {
      navigate(await signIn(picked), { replace: true });
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'sign-in failed'));
      setEntering(null);
    }
  };

  return (
    <div className="login grain warp">
      <div className="login__inner">
        <header className="login__head">
          <Link to="/" className="login__wordmark">Breadcrumbs</Link>
          <p className="stamp-type login__sub">Proving factory records without publishing them</p>
        </header>

        <h1 className="login__title">Who are you signing in as?</h1>
        <p className="lead login__lede">
          Pick a person to see the product through their eyes. There is no password:
          one press signs you in, and each person only sees what their job allows.
        </p>

        <div className="login__tour">
          <div>
            <p className="login__tourhead">First time here?</p>
            <p className="small login__tournote">
              {/* Counted, not typed. It said nine while the walkthrough had ten,
                  which is the sort of thing that goes stale the first time a
                  step is added and nobody thinks to look here. */}
              {TOUR.length} steps, start to finish. It signs you in as each person in
              turn, so you do not have to know who to pick.
            </p>
          </div>
          <StartWalkthrough className="btn btn--primary" />
        </div>

        <Result query={roles} pendingLabel="Asking the API which roles exist">
          {(options) => (
            <ul className="roles">
              {options.map((r, i) => (
                <li key={r.role}>
                  <button
                    type="button"
                    className={`role ${entering === r.role ? 'is-picked' : ''}`}
                    onClick={() => enter(r)}
                    disabled={entering !== null}
                    aria-busy={entering === r.role}
                    style={{ animationDelay: `${i * 55}ms` }}
                  >
                    <span className="role__n mono">{String(i + 1).padStart(2, '0')}</span>
                    <span className="role__body">
                      <span className="role__label">{r.label}</span>
                      <span className="role__org">{r.person} · {r.org}</span>
                      <span className="role__summary">{r.summary}</span>
                    </span>
                    <span className="role__go" aria-hidden="true">
                      {entering === r.role ? 'Signing in…' : 'Sign in'}
                      <ArrowRight size={15} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Result>

        {failure && <div className="login__failure"><Failed error={failure} /></div>}

        <div className="login__actions">
          <Link to="/verify" className="login__nolink">
            Have a receipt link? Check it without signing in
          </Link>
        </div>
      </div>
    </div>
  );
}
