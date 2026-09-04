import { Suspense, lazy, useEffect } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { Loading } from './components/Loading';
import { RouteTransition } from './components/RouteTransition';
import { Shell } from './components/Shell';
import { TourBar } from './components/TourBar';
import { useSession } from './lib/session';
import Landing from './pages/Landing';
import Login from './pages/Login';

// The landing page and the sign-in are the two ways in, so they ship with the
// shell. Everything behind the door is fetched when it is first opened, which
// is what gives the loading state a job and keeps the entry bundle small.
const Access = lazy(() => import('./pages/Access'));
const Anchor = lazy(() => import('./pages/Anchor'));
const AuditorBench = lazy(() => import('./pages/AuditorBench'));
const Chamber = lazy(() => import('./pages/Chamber'));
const GateDecisionPage = lazy(() => import('./pages/GateDecision'));
const LedgerExplorer = lazy(() => import('./pages/LedgerExplorer'));
const Lightbox = lazy(() => import('./pages/Lightbox'));
const LoomFloor = lazy(() => import('./pages/LoomFloor'));
const ModelRegistry = lazy(() => import('./pages/ModelRegistry'));
const Observatory = lazy(() => import('./pages/Observatory'));
const Periods = lazy(() => import('./pages/Periods'));
const Records = lazy(() => import('./pages/Records'));
const RecordDetail = lazy(() => import('./pages/RecordDetail'));
const Upload = lazy(() => import('./pages/Upload'));
const VerifyResult = lazy(() => import('./pages/VerifyResult'));

/** Every route change starts at the top; only the landing page owns its scroll. */
function ScrollReset() {
  const { pathname } = useLocation();
  useEffect(() => {
    if (pathname !== '/') window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function Protected({ children }: { children: React.ReactNode }) {
  const { role } = useSession();
  const location = useLocation();
  if (!role) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}

export default function App() {
  const { pathname } = useLocation();

  // The landing page runs a pinned, scrubbed narrative of its own, so it
  // arrives plainly rather than through the loading thread.
  const routes = (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        {/* With a receipt identifier this is a public check that needs no
            account; without one it is the live prover for whoever holds a grant. */}
        <Route path="/verify" element={<VerifyResult />} />
        <Route path="/verify/:id" element={<VerifyResult />} />

        <Route element={<Protected><Shell /></Protected>}>
          <Route path="/factory/dashboard" element={<LoomFloor />} />
          <Route path="/factory/upload" element={<Upload />} />
          <Route path="/factory/records" element={<Records />} />
          <Route path="/factory/records/:id" element={<RecordDetail />} />
          <Route path="/factory/access" element={<Access />} />
          <Route path="/buyer/portal" element={<Lightbox />} />
          <Route path="/auditor/workspace" element={<AuditorBench />} />
          <Route path="/governance" element={<Chamber />} />
          <Route path="/regulator" element={<Observatory />} />
          <Route path="/model/gate" element={<GateDecisionPage />} />
          <Route path="/model/gate/:id" element={<GateDecisionPage />} />
          <Route path="/model/registry" element={<ModelRegistry />} />
          <Route path="/periods" element={<Periods />} />
          <Route path="/anchor" element={<Anchor />} />
          <Route path="/ledger" element={<LedgerExplorer />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );

  return (
    <>
      <ScrollReset />
      {pathname === '/' ? routes : <RouteTransition>{routes}</RouteTransition>}
      {/* Outside the transition stage: the walkthrough is the one thing that
          must survive a route change without being animated out with it. */}
      <TourBar />
    </>
  );
}
