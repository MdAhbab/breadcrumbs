import { ShieldCheck } from 'lucide-react';
import { useState } from 'react';

import { HashChip, LedgerRow, Seal } from '../components/ui';
import { BLOCKS, CHAIN_HEIGHT } from '../lib/data';
import { commas, dateTime } from '../lib/format';
import './ledger.css';

/**
 * The ledger, as a bolt.
 *
 * A block list is the obvious rendering and the least evocative one. Here the
 * chain is a continuous woven strip you scrub along: each block is a segment,
 * its channel decides its band, and an invalid transaction shows as a broken
 * thread rather than a red row buried in a table.
 */
export default function LedgerExplorer() {
  const [selected, setSelected] = useState(BLOCKS[0].number);
  const [channel, setChannel] = useState<'all' | string>('all');

  const shown = channel === 'all' ? BLOCKS : BLOCKS.filter((b) => b.channel === channel);
  const block = BLOCKS.find((b) => b.number === selected) ?? BLOCKS[0];
  const channels = Array.from(new Set(BLOCKS.map((b) => b.channel)));

  return (
    <div className="led">
      <header className="led__head">
        <div>
          <p className="stamp-type led__eyebrow">Two channels · height {commas(CHAIN_HEIGHT)}</p>
          <h1>The bolt</h1>
          <p className="lead led__lede">
            Every block since the genesis of these channels, in order. Scrub along the
            selvedge to inspect one.
          </p>
        </div>
        <div className="led__integrity">
          <ShieldCheck size={16} />
          <div>
            <p className="led__int-head">Chain verified</p>
            <p className="small led__int-body">
              Every block re-hashed and matched against its committed value.
            </p>
          </div>
        </div>
      </header>

      <div className="led__filters">
        <button
          type="button"
          className={`chip ${channel === 'all' ? 'is-on' : ''}`}
          onClick={() => setChannel('all')}
        >
          all channels
        </button>
        {channels.map((c) => (
          <button
            key={c}
            type="button"
            className={`chip ${channel === c ? 'is-on' : ''}`}
            onClick={() => setChannel(c)}
          >
            {c}
          </button>
        ))}
      </div>

      {/* -- the woven strip --------------------------------------------- */}
      <div className="strip-scroll scroll-x">
        <ol className="chainstrip">
          {shown.map((b) => {
            const bad = b.txs.some((t) => !t.valid);
            return (
              <li key={b.number}>
                <button
                  type="button"
                  className={`seg ${b.number === selected ? 'is-on' : ''} ${bad ? 'is-broken' : ''} seg--${b.channel === 'model-channel' ? 'model' : 'docs'}`}
                  onClick={() => setSelected(b.number)}
                  aria-label={`Block ${b.number}`}
                >
                  <span className="seg__weft" aria-hidden="true">
                    {Array.from({ length: 6 }, (_, i) => <span key={i} />)}
                  </span>
                  <span className="mono seg__n">{b.number.toString().slice(-3)}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>
      <p className="small led__legend">
        <span className="key key--docs" /> document channel
        <span className="key key--model" /> model channel
        <span className="key key--broken" /> contains an invalidated transaction
      </p>

      {/* -- the selected block ------------------------------------------ */}
      <section className="blockcard">
        <div className="blockcard__head">
          <h2 className="mono blockcard__n">block #{commas(block.number)}</h2>
          <Seal tone={block.txs.every((t) => t.valid) ? 'sealed' : 'broken'}>
            {block.txs.every((t) => t.valid) ? 'all valid' : 'contains invalid'}
          </Seal>
        </div>

        <div className="blockcard__grid">
          <div>
            <LedgerRow label="Channel"><span className="mono">{block.channel}</span></LedgerRow>
            <LedgerRow label="Timestamp">{dateTime(block.timestamp)}</LedgerRow>
            <LedgerRow label="Proposer"><span className="mono">{block.proposer}</span></LedgerRow>
            <LedgerRow label="Block hash"><HashChip value={block.hash} /></LedgerRow>
            <LedgerRow label="Previous"><HashChip value={block.previousHash} /></LedgerRow>
          </div>

          <div>
            <p className="stamp-type blockcard__label">Transactions</p>
            {block.txs.map((t) => (
              <div key={t.txId} className={`tx ${t.valid ? '' : 'is-bad'}`}>
                <div className="tx__top">
                  <span className="mono tx__cc">{t.chaincode}</span>
                  <span className="tx__fn">{t.fn.replace(/_/g, ' ')}</span>
                  <span className={`tx__code stamp-type ${t.valid ? 'ok' : 'bad'}`}>{t.code}</span>
                </div>
                <p className="small tx__sub">
                  submitted by <span className="mono">{t.submitter}</span>
                </p>
                <p className="small tx__end">
                  endorsed by {t.endorsers.join(', ')}
                </p>
                <HashChip value={t.txId} />
                {!t.valid && (
                  <p className="small tx__why">
                    Kept in the block rather than dropped. The ledger records what was
                    attempted, not only what succeeded.
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
