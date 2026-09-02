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
          <p className="stamp-type per__eyebrow">Anchor · RSA accumulator</p>
          <h1>One integer for the whole ledger</h1>
          <p className="lead per__lede">
            Every committed record and every period seal folds into a single value.
            Checking that one of them is inside takes constant time — the same work
            whether the set holds ten elements or ten million.
          </p>
        </div>
      </header>

      <Result query={world} pendingLabel="Reading the accumulator">
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
              <h2 className="per__h2">Proof of absence</h2>
              <p className="per__note">
                A Merkle tree can prove a document is in a set. It cannot prove one
                is not. This can — and it is the difference between &ldquo;we have no
                record of that certificate&rdquo; and a statement somebody can check.
              </p>
              <AbsenceProof />
            </section>
          </>
        )}
      </Result>
    </div>
  );
}
