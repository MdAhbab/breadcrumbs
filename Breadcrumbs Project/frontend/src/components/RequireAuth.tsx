import { Navigate, useLocation } from 'react-router-dom';

import { loadSession } from '../lib/api';

/** Sends an unauthenticated visitor to sign in, remembering where they were. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!loadSession()) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }
  return <>{children}</>;
}
