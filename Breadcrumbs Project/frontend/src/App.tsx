/*
 * Routes.
 *
 * Every screen in designs_instructions.md has an entry here, including the ones
 * not built yet — they render a Placeholder naming the section of the spec that
 * describes them. That is deliberate: a route that 404s tells you nothing, and
 * a route that says "§8.1 — Continuity Gate Decision" tells whoever picks this
 * up exactly what to build and where the specification is.
 */

import { Navigate, Route, Routes } from 'react-router-dom';

import { Placeholder } from './components/Placeholder';
import { RequireAuth } from './components/RequireAuth';
import { Shell } from './components/Shell';
import { loadSession } from './lib/api';

export default function App() {
  const session = loadSession();

  return (
    <Routes>
      {/* public */}
      <Route path="/" element={<Placeholder title="Landing" spec="§9 — parallax and scroll choreography" />} />
      <Route path="/login" element={<Placeholder title="Sign in" spec="§7.1" />} />
      <Route path="/verify" element={<Placeholder title="Public verification" spec="§8.7 — no login, mobile-first" />} />
      <Route path="/verify/:id" element={<Placeholder title="Verification result" spec="§7.7 — the five-second test" />} />

      {/* authenticated */}
      <Route element={<RequireAuth><Shell /></RequireAuth>}>
        <Route path="/factory/dashboard" element={<Placeholder title="Factory dashboard" spec="§7.2" />} />
        <Route path="/factory/upload" element={<Placeholder title="Upload & commit" spec="§7.3 — five-step commit stepper" />} />
        <Route path="/factory/records" element={<Placeholder title="Records" spec="§7.4" />} />
        <Route path="/factory/records/:id" element={<Placeholder title="Record detail" spec="§7.4" />} />
        <Route path="/factory/access" element={<Placeholder title="Access grants" spec="§7.5" />} />

        <Route path="/buyer/portal" element={<Placeholder title="Request portal" spec="§7.6" />} />
        <Route path="/auditor/workspace" element={<Placeholder title="Auditor batch workspace" spec="§7.8" />} />

        <Route path="/governance" element={<Placeholder title="Governance console" spec="§7.9" />} />
        <Route path="/governance/members" element={<Placeholder title="Member directory" spec="§7.9" />} />
        <Route path="/governance/enrol" element={<Placeholder title="Member enrolment" spec="§8.8 — four-step wizard" />} />
        <Route path="/ops/sla" element={<Placeholder title="SLA & operations" spec="§7.10" />} />
        <Route path="/ops/incidents/:id" element={<Placeholder title="Incident detail" spec="§8.12" />} />
        <Route path="/regulator" element={<Placeholder title="Regulator observer" spec="§7.11" />} />

        {/* the learning plane — the screens the Figma build has none of */}
        <Route path="/model/gate/:id" element={<Placeholder title="Continuity Gate decision" spec="§8.1 — the demo's money shot" />} />
        <Route path="/model/registry" element={<Placeholder title="Model registry & lineage" spec="§8.2" />} />
        <Route path="/model/rounds" element={<Placeholder title="Federated round monitor" spec="§8.3" />} />
        <Route path="/model/benchmarks" element={<Placeholder title="Benchmark commitment" spec="§8.4" />} />
        <Route path="/model/memory-bank" element={<Placeholder title="Memory bank inspector" spec="§8.5" />} />
        <Route path="/ledger" element={<Placeholder title="Ledger explorer" spec="§8.6" />} />
        <Route path="/ledger/block/:n" element={<Placeholder title="Block detail" spec="§8.6" />} />

        <Route path="/settings" element={<Placeholder title="Settings" spec="§8.9" />} />
        <Route path="/settings/keys" element={<Placeholder title="Key management" spec="§8.9" />} />
        <Route path="/settings/schemas" element={<Placeholder title="Schema registry" spec="§8.13" />} />
        <Route path="/notifications" element={<Placeholder title="Notifications" spec="§8.10" />} />
        <Route path="/search" element={<Placeholder title="Search" spec="§8.11 — ⌘K" />} />
      </Route>

      <Route path="/403" element={<Placeholder title="Scope denied" spec="§8.14" />} />
      <Route path="/404" element={<Placeholder title="Not found" spec="§8.14" />} />
      <Route
        path="*"
        element={<Navigate to={session ? '/404' : '/'} replace />}
      />
    </Routes>
  );
}
