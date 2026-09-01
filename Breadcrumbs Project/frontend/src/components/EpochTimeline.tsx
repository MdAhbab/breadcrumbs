import { Clock, Layers } from 'lucide-react';

import { EPOCHS, MINIMUM_ITERATIONS, type AnchorState } from '../lib/anchor';
import { commas, dateTime, shortHash } from '../lib/format';
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
 */
export function EpochTimeline({ state }: { state: AnchorState }) {
  if (!state.installed) {
    return (
      <section className="epochs epochs--off">
        <p className="epochs__title">No accumulator on this channel</p>
        <p className="small">{state.reason}</p>
      </section>
    );
  }

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
          <span className="epochs__n">{state.modulus_bits}</span>
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

      <p className="small epochs__dealer">
        Parameters from a trusted-dealer ceremony run by {state.dealer}. Whoever
        held the factorisation could forge an accumulator witness, which is why
        no verification here rests on one alone.
      </p>

      <ol className="etl">
        {[...EPOCHS].reverse().map((e) => {
          const short = e.beacon && e.beacon.iterations < MINIMUM_ITERATIONS;
          return (
            <li key={e.epoch} className={`etl__item ${short ? 'is-short' : ''}`}>
              <span className="etl__dot" aria-hidden="true" />
              <div className="etl__body">
                <div className="etl__head">
                  <span className="etl__epoch mono">epoch {e.epoch}</span>
                  <span className="small etl__when">{dateTime(e.sealed_at)}</span>
                </div>

                <div className="etl__figs">
                  <span className="small"><Layers size={12} /> {e.element_count} folded in</span>
                  <span className="small">set size {e.size}</span>
                  <span className="mono etl__val">{shortHash(e.value_hex)}</span>
                </div>

                {e.beacon ? (
                  <div className={`etl__beacon ${short ? 'is-short' : ''}`}>
                    <Clock size={12} />
                    <span className="mono">{commas(e.beacon.iterations)}</span>
                    <span className="small">sequential squarings</span>
                    {short ? (
                      <Seal tone="broken">
                        below the agreed {commas(MINIMUM_ITERATIONS)}
                      </Seal>
                    ) : (
                      <Seal tone="sealed">delay proof verified</Seal>
                    )}
                  </div>
                ) : (
                  <div className="etl__beacon is-absent">
                    <Clock size={12} />
                    <span className="small">
                      No beacon. This epoch&rsquo;s order is proved; the time that
                      passed before it is not.
                    </span>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
