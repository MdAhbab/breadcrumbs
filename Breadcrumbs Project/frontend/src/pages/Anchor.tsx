import { AbsenceProof } from '../components/AbsenceProof';
import { EpochTimeline } from '../components/EpochTimeline';
import { Result } from '../components/states';
import { api, type AnchorGroup, type AnchorState, type Epoch } from '../lib/api';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import './periods.css';

/**
 * The accumulator: one integer that commits the whole record set.
 *
 * Open to the regulator as well as the consortium, because the accumulator is a
 * fact about the network rather than about any factory's documents — and an
 * observer that can see nothing at all cannot observe.
 */
export default function Anchor() {
  const { role } = useSession();
  const world = useApi(
    () => Promise.all([api.anchorState(), api.epochs(), api.anchorGroup()]) as
      Promise<[AnchorState, Epoch[], AnchorGroup]>,
    [],
  );

  return (
    <div className="periods">
      <header className="per__head">
        <div>
          <p className="stamp-type per__eyebrow">Has anything been tampered with?</p>
          <h1>One number that covers everything</h1>
          <p className="lead per__lede">
            Every record and every closed month folds into a single number. Asking
            whether something is inside it takes the same amount of work whether there
            are ten of them or ten million. Unusually, you can also prove that
            something is <em>not</em> in there.
          </p>
        </div>
      </header>

      <Result query={world} pendingLabel="Reading the check number">
        {([state, epochs, group]) => (
          <>
            <EpochTimeline
              state={state}
              epochs={epochs}
              group={group}
              canPublish={role?.id === 'consortium'}
              onPublished={world.reload}
            />

            <section className="per__section">
              <h2 className="per__h2">Proving something does not exist</h2>
              <p className="per__note">
                Showing that a document <em>is</em> on the ledger is the easy direction.
                Showing that one is not there, that a certificate was never issued or
                that a month has nothing hidden in it, is the hard one. This does it. It is
                the difference between &ldquo;we have no record of that&rdquo; and
                something the other side can check for themselves.
              </p>
              <AbsenceProof />
            </section>
          </>
        )}
      </Result>
    </div>
  );
}
