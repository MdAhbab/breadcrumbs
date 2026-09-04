import { Clock, Layers } from 'lucide-react';
import { useState } from 'react';

import { ApiError, api, type AnchorGroup, type AnchorState, type Epoch } from '../lib/api';
import { commas, dateTime, shortHash } from '../lib/format';
import { Failed } from './states';
import { Plain, Tech } from './Tech';
import { Seal } from './ui';
import './mechanisms.css';

/**
 * The accumulator over time: one integer, and how it got there.
 *
 * Two honest states are drawn rather than hidden. An epoch with no beacon has
 * proved its order and nothing about elapsed time. An epoch whose beacon claims
 * fewer iterations than the consortium agreed has proved less work than the
 * rule asks for, and saying "verified" over it would be the interface inventing
 * a guarantee the ledger never made.
 *
 * The agreed minimum comes from the API rather than being a constant here, and
 * that matters more than it looks: `publish_beacon` reads the minimum out of the
 * arguments it is handed rather than out of channel configuration, so the API is
 * currently the only thing holding the bar steady. A number hardcoded in the
 * frontend could disagree with the one the contract was actually given and this
 * panel would report a pass that never happened.
 */
export function EpochTimeline({
  state,
  epochs,
  group,
  canPublish = false,
  onPublished,
}: {
  state: AnchorState;
  epochs: Epoch[];
  group: AnchorGroup;
  /** The consortium may attach a delay proof to an epoch that has none. */
  canPublish?: boolean;
  onPublished?: () => void;
}) {
  const [busy, setBusy] = useState<number | null>(null);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const publish = async (epoch: number, iterations: number) => {
    setBusy(epoch);
    setFailure(null);
    try {
      await api.publishBeacon(epoch, iterations);
      onPublished?.();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'the beacon was refused'));
    } finally {
      setBusy(null);
    }
  };

  if (!state.installed) {
    return (
      <section className="epochs epochs--off">
        <p className="epochs__title">The tamper check is not set up here yet</p>
        <p className="small">
          {state.reason ?? 'Nothing has been set up on this part of the network, so there is nothing to add records to.'}
        </p>
      </section>
    );
  }

  const minimum = state.minimum_iterations ?? 0;

  return (
    <section className="epochs">
      <div className="epochs__state">
        <div className="epochs__figure">
          <span className="epochs__n">{state.epoch}</span>
          <span className="stamp-type">times updated</span>
        </div>
        <div className="epochs__figure">
          <span className="epochs__n">{commas(state.size ?? 0)}</span>
          <span className="stamp-type">things it covers</span>
        </div>
        <Tech>
          <div className="epochs__figure">
            <span className="epochs__n">{group.params?.modulus_bits ?? 'not set'}</span>
            <span className="stamp-type">bit modulus</span>
          </div>
        </Tech>
        <div className="epochs__value">
          <span className="stamp-type">The number itself</span>
          <span className="mono">{shortHash(state.value_hex ?? '')}</span>
          <span className="small">
            This single number stands for everything listed above. Checking whether one
            record is inside it takes the same work whether there are ten of them or
            ten million.
          </span>
        </div>
      </div>

      {group.transcript && (
        <p className="small epochs__dealer">
          The starting numbers were set up by {group.transcript.dealer}, using randomness
          contributed by {group.transcript.contributors.join(', ')}. Whoever held the
          original secret from that setup could fake one of the three checks, which is
          exactly why nothing here relies on that check by itself.
        </p>
      )}

      {failure && <Failed error={failure} />}

      <ol className="etl">
        {[...epochs].reverse().map((e) => {
          const short = e.beacon !== undefined && e.beacon.iterations < minimum;
          return (
            <li key={e.epoch} className={`etl__item ${short ? 'is-short' : ''}`}>
              <span className="etl__dot" aria-hidden="true" />
              <div className="etl__body">
                <div className="etl__head">
                  <span className="etl__epoch mono">update {e.epoch}</span>
                  <span className="small etl__when">{dateTime(e.sealed_at)}</span>
                </div>

                <div className="etl__figs">
                  <span className="small">
                    <Layers size={12} /> {commas(e.element_count)} added
                  </span>
                  <span className="small">{commas(e.size)} covered in total</span>
                  <Tech>
                    <span className="mono etl__val">{shortHash(e.accumulator_hex)}</span>
                  </Tech>
                </div>

                {e.beacon ? (
                  <div className={`etl__beacon ${short ? 'is-short' : ''}`}>
                    <Clock size={12} />
                    <Tech>
                      <span className="mono">{commas(e.beacon.iterations)}</span>
                      <span className="small">sequential squarings</span>
                    </Tech>
                    <Plain>
                      <span className="small">
                        Proof that real time passed before this update
                      </span>
                    </Plain>
                    {short ? (
                      <Seal tone="broken">less work than agreed</Seal>
                    ) : (
                      <Seal tone="sealed">checked</Seal>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="etl__beacon is-absent">
                      <Clock size={12} />
                      <span className="small">
                        No time proof yet. The order these were added in is proved.
                        How much time passed before it is not.
                      </span>
                    </div>
                    {canPublish && minimum > 0 && (
                      <div className="etl__publish">
                        <button
                          type="button"
                          className="btn btn--secondary btn--sm"
                          disabled={busy !== null}
                          onClick={() => void publish(e.epoch, minimum)}
                        >
                          {busy === e.epoch ? 'Working…' : 'Publish a time proof'}
                        </button>
                        <p className="small">
                          This really does the work: a calculation that cannot be
                          hurried, even with more machines. It takes a couple of seconds
                          to produce and about two milliseconds for anyone to check.
                          <Tech> {commas(minimum)} sequential squarings.</Tech>
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
