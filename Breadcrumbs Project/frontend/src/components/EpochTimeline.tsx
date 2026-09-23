import { Clock, Layers } from 'lucide-react';
import { useState } from 'react';

import { ApiError, api, type AnchorGroup, type AnchorState, type Epoch } from '../lib/api';
import { commas, dateTime, shortHash } from '../lib/format';
import { Failed } from './states';
import { Plain, Tech } from './Tech';
import { Seal } from './ui';
import './mechanisms.css';

/**
 * The tamper check over time: one fingerprint, and each update to it.
 *
 * Two honest states are drawn rather than hidden. An update with no time check
 * (beacon) says nothing about elapsed time. One whose beacon claims fewer
 * iterations than the consortium agreed has done less work than the rule asks
 * for, and "checked" over it would invent a guarantee the ledger never made.
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
          {state.reason ?? 'Nothing has been set up on this part of the network yet.'}
        </p>
      </section>
    );
  }

  const minimum = state.minimum_iterations ?? 0;

  return (
    <section className="epochs">
      <div className="epochs__state">
        <div className="epochs__figure">
          <span className="epochs__n">{commas(state.epoch ?? 0)}</span>
          <span className="stamp-type">updates</span>
        </div>
        <div className="epochs__figure">
          <span className="epochs__n">{commas(state.size ?? 0)}</span>
          <span className="stamp-type">documents and months covered</span>
        </div>
        <Tech>
          <div className="epochs__figure">
            <span className="epochs__n">{group.params?.modulus_bits ?? 'not set'}</span>
            <span className="stamp-type">bit modulus</span>
          </div>
        </Tech>
      </div>

      <Tech>
        <div className="epochs__value">
          <span className="stamp-type">Fingerprint</span>
          <span className="mono">{shortHash(state.value_hex ?? '')}</span>
        </div>
        {group.transcript && (
          <p className="small epochs__dealer">
            Set up by {group.transcript.dealer}, with randomness from{' '}
            {group.transcript.contributors.join(', ')}. Whoever held the setup secret
            could fake one of the three checks, so nothing relies on that check alone.
          </p>
        )}
      </Tech>

      {failure && <Failed error={failure} />}

      <ol className="etl">
        {[...epochs].reverse().map((e) => {
          const short = e.beacon !== undefined && e.beacon.iterations < minimum;
          return (
            <li key={e.epoch} className={`etl__item ${short ? 'is-short' : ''}`}>
              <span className="etl__dot" aria-hidden="true" />
              <div className="etl__body">
                <div className="etl__head">
                  <span className="etl__epoch">Update {commas(e.epoch)}</span>
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
                      <span className="small">Real time passed before this update</span>
                    </Plain>
                    {short ? (
                      <Seal tone="broken">less work than agreed</Seal>
                    ) : (
                      <Seal tone="sealed">Checked</Seal>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="etl__beacon is-absent">
                      <Clock size={12} />
                      <span className="small">Time not checked yet</span>
                    </div>
                    {canPublish && minimum > 0 && (
                      <div className="etl__publish">
                        <button
                          type="button"
                          className="btn btn--secondary btn--sm"
                          disabled={busy !== null}
                          onClick={() => void publish(e.epoch, minimum)}
                        >
                          {busy === e.epoch ? 'Working…' : 'Add a time check'}
                        </button>
                        <p className="small">
                          Takes a few seconds.
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
