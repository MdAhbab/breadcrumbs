import { AbsenceProof } from '../components/AbsenceProof';
import { EpochTimeline } from '../components/EpochTimeline';
import { Result } from '../components/states';
import { api, type AnchorGroup, type AnchorState, type Epoch } from '../lib/api';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import '../components/mechanisms.css';

/**
 * Tamper check: one fingerprint that covers every document and closed month.
 *
 * Open to the regulator as well as the consortium, because it is a fact about
 * the network rather than about any factory's documents. An observer that can
 * see nothing at all cannot observe. Page layout lives in mechanisms.css
 * under "tamper check page".
 */
export default function Anchor() {
  const { role } = useSession();
  const world = useApi(
    () => Promise.all([api.anchorState(), api.epochs(), api.anchorGroup()]) as
      Promise<[AnchorState, Epoch[], AnchorGroup]>,
    [],
  );

  return (
    <div className="tamper">
      <header className="tamper__head">
        <h1>Tamper check</h1>
        <p className="lead tamper__lede">
          One fingerprint covers every document and closed month on the ledger. If
          anything had been changed, this check would fail.
        </p>
      </header>

      <Result query={world} pendingLabel="Reading the tamper check">
        {([state, epochs, group]) => (
          <>
            <EpochTimeline
              state={state}
              epochs={epochs}
              group={group}
              canPublish={role?.id === 'consortium'}
              onPublished={world.reload}
            />

            <section className="tamper__section">
              <h2 className="tamper__h2">Check that something was never filed</h2>
              <AbsenceProof />
            </section>
          </>
        )}
      </Result>
    </div>
  );
}
