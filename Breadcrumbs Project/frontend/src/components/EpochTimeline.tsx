import { Clock, Layers } from 'lucide-react';
import { useState } from 'react';

import { ApiError, api, type AnchorGroup, type AnchorState, type Epoch } from '../lib/api';
import { commas, dateTime, shortHash } from '../lib/format';
import { Failed } from './states';
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
        <p className="epochs__title">No accumulator on this channel</p>
        <p className="small">
          {state.reason ?? 'No parameters have been installed, so there is nothing to fold into.'}
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
          <span className="stamp-type">epochs folded</span>
        </div>
        <div className="epochs__figure">
          <span className="epochs__n">{commas(state.size ?? 0)}</span>
          <span className="stamp-type">elements committed</span>
        </div>
        <div className="epochs__figure">
          <span className="epochs__n">{group.params?.modulus_bits ?? '—'}</span>
          <span className="stamp-type">bit modulus</span>
        </div>
        <div className="epochs__value">
          <span className="stamp-type">Accumulator value</span>
          <span className="mono">{shortHash(state.value_hex ?? '')}</span>
          <span className="small">
            One integer commits every element above. Verifying one takes the same
            time whether the set holds ten or ten million.
          </span>
        </div>
      </div>

      {group.transcript && (
        <p className="small epochs__dealer">
          Parameters from a trusted-dealer ceremony run by {group.transcript.dealer},
          with entropy from {group.transcript.contributors.join(', ')}. Whoever held
          the factorisation could forge an accumulator witness, which is why no
          verification here rests on one alone.
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
                  <span className="etl__epoch mono">epoch {e.epoch}</span>
                  <span className="small etl__when">{dateTime(e.sealed_at)}</span>
                </div>

                <div className="etl__figs">
                  <span className="small">
                    <Layers size={12} /> {commas(e.element_count)} folded in
                  </span>
                  <span className="small">set size {commas(e.size)}</span>
                  <span className="mono etl__val">{shortHash(e.accumulator_hex)}</span>
                </div>

                {e.beacon ? (
                  <div className={`etl__beacon ${short ? 'is-short' : ''}`}>
                    <Clock size={12} />
                    <span className="mono">{commas(e.beacon.iterations)}</span>
                    <span className="small">sequential squarings</span>
                    {short ? (
                      <Seal tone="broken">below the agreed {commas(minimum)}</Seal>
                    ) : (
                      <Seal tone="sealed">delay proof verified</Seal>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="etl__beacon is-absent">
                      <Clock size={12} />
                      <span className="small">
                        No beacon. This epoch&rsquo;s order is proved; the time that
                        passed before it is not.
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
                          {busy === e.epoch
                            ? 'Squaring…'
                            : `Publish a delay proof (${commas(minimum)} squarings)`}
                        </button>
                        <p className="small">
                          This really does the work. It takes a couple of seconds to
                          produce and about two milliseconds to check — which is the
                          whole point of a verifiable delay function.
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
