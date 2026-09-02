import { ArrowUpRight } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { api, type Block, type Channel } from '../lib/api';
import { commas, shortHash } from '../lib/format';
import { DUR } from '../lib/motion';
import { useApi } from '../lib/useApi';
import { useReducedMotion } from '../lib/useMotionPref';
import { Modal, ModalHead } from './ui';
import './chainstatus.css';

const DOC_CHANNEL = 'documents-apex-primark';
const POLL_MS = 10_000;

/**
 * The state of the chain, as a control.
 *
 * The selvedge is the self-finished edge of woven fabric — the tightly bound
 * border that stops the cloth unravelling — and it is the right figure for a
 * ledger. Here it is a row of ticks accumulating toward the head: one per
 * block, brightest where the cloth is newest.
 *
 * The height is the real height, polled from `/api/ledger/channels`, and the
 * weave-in pulse fires only when it genuinely changes. It used to increment on
 * a timer with a random interval, which made the one element in the product
 * that claimed to be live the one element that was purely decorative — and it
 * would have kept counting merrily upward with the API switched off.
 */
export function ChainStatus({ variant = 'nav' }: { variant?: 'nav' | 'bar' }) {
  const reduced = useReducedMotion();
  const [open, setOpen] = useState(false);
  const [pulse, setPulse] = useState(false);
  const [tick, setTick] = useState(0);
  const previous = useRef<number | null>(null);

  const chain = useApi(() => api.channels(), [tick]);
  const blocks = useApi(
    () => (open ? api.blocks(DOC_CHANNEL, 9) : Promise.resolve([] as Block[])),
    [open, tick],
  );

  // Poll rather than simulate. Nothing here invents a block.
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), POLL_MS);
    return () => window.clearInterval(id);
  }, []);

  const documents: Channel | undefined =
    chain.data?.find((c) => c.channel === DOC_CHANNEL) ?? chain.data?.[0];
  const height = documents?.height ?? null;
  const verified = chain.data?.every((c) => c.integrity_ok) ?? false;

  useEffect(() => {
    if (height === null) return;
    if (previous.current !== null && height > previous.current && !reduced) {
      setPulse(true);
      const id = window.setTimeout(() => setPulse(false), DUR.weave * 1000);
      previous.current = height;
      return () => window.clearTimeout(id);
    }
    previous.current = height;
  }, [height, reduced]);

  const ticks = variant === 'nav' ? 30 : 12;
  const unreachable = chain.error !== null;
  const shown = height === null ? '—' : commas(height);

  return (
    <>
      <button
        type="button"
        className={`chainstat chainstat--${variant} ${pulse ? 'is-pulse' : ''} ${
          unreachable ? 'is-down' : ''
        }`}
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-label={
          unreachable
            ? 'The ledger is not answering. Show details.'
            : `Ledger height ${shown}, chain ${verified ? 'verified' : 'unverified'}. Show recent blocks.`
        }
      >
        <span className="chainstat__meta">
          <span className="stamp-type chainstat__label">
            {variant === 'nav' ? 'Ledger height' : 'Height'}
          </span>
          <span
            className={`chainstat__dot ${verified ? '' : 'is-off'}`}
            aria-hidden="true"
          />
        </span>

        <span className="mono chainstat__height">
          <span aria-live="polite">{shown}</span>
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
            eyebrow={
              unreachable
                ? 'the API is not answering'
                : `height ${shown} · chain ${verified ? 'verified' : 'NOT verified'}`
            }
            title="Recent blocks"
            onClose={() => setOpen(false)}
          />
          <div className="modal__body">
            {unreachable ? (
              <p className="chainstat__note">{chain.error?.message}</p>
            ) : blocks.data && blocks.data.length > 0 ? (
              <ul className="chainstat__list">
                {blocks.data.map((b) => {
                  const tx = b.transactions[0];
                  return (
                    <li key={b.number} className="chainstat__row">
                      <span className="mono chainstat__num">#{commas(b.number)}</span>
                      <span className="chainstat__cc">{tx ? tx.chaincode : 'config'}</span>
                      <span className={`chainstat__flag ${!tx || tx.valid ? 'ok' : 'bad'}`}>
                        {!tx || tx.valid ? 'valid' : 'invalid'}
                      </span>
                      <span className="mono chainstat__hash">{shortHash(b.block_hash)}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="chainstat__note">Reading the chain…</p>
            )}
          </div>
          <footer className="modal__foot">
            <span className="small chainstat__note">
              {verified
                ? 'Every block re-hashed and matched.'
                : 'Integrity check has not passed on every channel.'}
            </span>
            <Link to="/ledger" className="btn btn--primary btn--sm" onClick={() => setOpen(false)}>
              Open the ledger <ArrowUpRight size={14} />
            </Link>
          </footer>
        </Modal>
      )}
    </>
  );
}
