import { ArrowUpRight } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { BLOCKS, CHAIN_HEIGHT } from '../lib/data';
import { commas, shortHash } from '../lib/format';
import { DUR } from '../lib/motion';
import { useReducedMotion } from '../lib/useMotionPref';
import { Modal, ModalHead } from './ui';
import './chainstatus.css';

/**
 * The state of the chain, as a control.
 *
 * The selvedge is the self-finished edge of woven fabric — the tightly bound
 * border that stops the cloth unravelling — and it is the right figure for a
 * ledger. Here it is a row of ticks accumulating toward the head: one per
 * block, brightest where the cloth is newest. When a block lands, a tick weaves
 * itself in and the height lifts.
 *
 * It is a labelled button, not a hover target. The previous version was a bare
 * strip down the edge of the screen whose only affordance was hovering over
 * dead space — invisible to touch, and unreadable as anything but a glitch.
 */
export function ChainStatus({ variant = 'nav' }: { variant?: 'nav' | 'bar' }) {
  const reduced = useReducedMotion();
  const [height, setHeight] = useState(CHAIN_HEIGHT);
  const [open, setOpen] = useState(false);
  const [pulse, setPulse] = useState(false);
  const timer = useRef<number>();

  // A block lands every so often. This is the only thing in the product that
  // makes it feel attached to something running.
  useEffect(() => {
    if (reduced) return;
    const tick = () => {
      setHeight((h) => h + 1);
      setPulse(true);
      window.setTimeout(() => setPulse(false), DUR.weave * 1000);
      timer.current = window.setTimeout(tick, 9000 + Math.random() * 7000);
    };
    timer.current = window.setTimeout(tick, 6000);
    return () => window.clearTimeout(timer.current);
  }, [reduced]);

  const ticks = variant === 'nav' ? 30 : 12;

  return (
    <>
      <button
        type="button"
        className={`chainstat chainstat--${variant} ${pulse ? 'is-pulse' : ''}`}
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-label={`Ledger height ${commas(height)}, chain verified. Show recent blocks.`}
      >
        <span className="chainstat__meta">
          <span className="stamp-type chainstat__label">
            {variant === 'nav' ? 'Ledger height' : 'Height'}
          </span>
          <span className="chainstat__dot" aria-hidden="true" />
        </span>

        <span className="mono chainstat__height">
          <span aria-live="polite">{commas(height)}</span>
        </span>

        <span className="chainstat__edge" aria-hidden="true">
          {Array.from({ length: ticks }, (_, i) => (
            <span
              key={i}
              className="chainstat__tick"
              style={{
                // Denser and brighter toward the head: the newest cloth.
                opacity: 0.16 + (i / (ticks - 1)) * 0.78,
                transform: `scaleY(${i % 7 === 0 ? 2.4 : i % 3 === 0 ? 1.7 : 1})`,
              }}
            />
          ))}
        </span>
      </button>

      {open && (
        <Modal label="Recent blocks" onClose={() => setOpen(false)}>
          <ModalHead
            eyebrow={`height ${commas(height)} · chain verified`}
            title="Recent blocks"
            onClose={() => setOpen(false)}
          />
          <div className="modal__body">
            <ul className="chainstat__list">
              {BLOCKS.slice(0, 9).map((b) => (
                <li key={b.number} className="chainstat__row">
                  <span className="mono chainstat__num">#{commas(b.number)}</span>
                  <span className="chainstat__cc">{b.txs[0].chaincode}</span>
                  <span className={`chainstat__flag ${b.txs[0].valid ? 'ok' : 'bad'}`}>
                    {b.txs[0].valid ? 'valid' : 'invalid'}
                  </span>
                  <span className="mono chainstat__hash">{shortHash(b.hash)}</span>
                </li>
              ))}
            </ul>
          </div>
          <footer className="modal__foot">
            <span className="small chainstat__note">Every block re-hashed and matched.</span>
            <Link to="/ledger" className="btn btn--primary btn--sm" onClick={() => setOpen(false)}>
              Open the ledger <ArrowUpRight size={14} />
            </Link>
          </footer>
        </Modal>
      )}
    </>
  );
}
