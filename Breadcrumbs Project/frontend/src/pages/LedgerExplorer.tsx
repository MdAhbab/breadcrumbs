import { ShieldAlert, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

import { Result } from '../components/states';
import { HashChip, LedgerRow, Seal } from '../components/ui';
import { api, type Block, type Channel } from '../lib/api';
import { commas, dateTime } from '../lib/format';
import { useApi } from '../lib/useApi';
import './ledger.css';

const WINDOW = 60;

/**
 * The ledger, as a bolt.
 *
 * A block list is the obvious rendering and the least evocative one. Here the
 * chain is a continuous woven strip you scrub along: each block is a segment,
 * its channel decides its band, and an invalid transaction shows as a broken
 * thread rather than a red row buried in a table.
 *
 * The integrity claim at the top is the result of `/api/ledger/verify`, which
 * walks every channel and re-hashes every block. It is a claim worth being
 * careful with: this panel used to print "Chain verified" unconditionally.
 */
export default function LedgerExplorer() {
  const [channel, setChannel] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);

  const chain = useApi(() => api.verifyChain(), []);
  const current = channel ?? chain.data?.channels[0]?.channel ?? null;
  const blocks = useApi(
    () => (current ? api.blocks(current, WINDOW, offset) : Promise.resolve([] as Block[])),
    [current, offset],
  );

  return (
    <div className="led">
      <Result query={chain} pendingLabel="Re-hashing every block">
        {(integrity) => (
          <>
            <header className="led__head">
              <div>
                <p className="stamp-type led__eyebrow">
                  {integrity.channels.length} channels ·{' '}
                  {commas(integrity.channels.reduce((a, c) => a + c.height, 0))} blocks
                </p>
                <h1>The bolt</h1>
                <p className="lead led__lede">
                  Every block since the genesis of these channels, in order. Scrub along
                  the selvedge to inspect one.
                </p>
              </div>
              <div className={`led__integrity ${integrity.ok ? '' : 'is-bad'}`}>
                {integrity.ok ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}
                <div>
                  <p className="led__int-head">
                    {integrity.ok ? 'Chain verified' : 'Integrity check FAILED'}
                  </p>
                  <p className="small led__int-body">
                    {integrity.ok
                      ? 'Every block re-hashed and matched against its committed value.'
                      : integrity.channels
                        .filter((c) => !c.integrity_ok)
                        .map((c) => `${c.channel}: ${c.integrity_detail}`)
                        .join(' · ')}
                  </p>
                </div>
              </div>
            </header>

            <div className="led__filters">
              {integrity.channels.map((c: Channel) => (
                <button
                  key={c.channel}
                  type="button"
                  className={`chip ${current === c.channel ? 'is-on' : ''}`}
                  onClick={() => { setChannel(c.channel); setOffset(0); setSelected(null); }}
                >
                  {c.channel} · {commas(c.height)}
                </button>
              ))}
            </div>

            <Result query={blocks} pendingLabel="Reading blocks">
              {(page) => {
                const block = page.find((b) => b.number === selected) ?? page[0];
                const height = integrity.channels.find((c) => c.channel === current)?.height ?? 0;
                return (
                  <>
                    <div className="strip-scroll scroll-x">
                      <ol className="chainstrip">
                        {page.map((b) => {
                          const bad = b.transactions.some((t) => !t.valid);
                          return (
                            <li key={b.number}>
                              <button
                                type="button"
                                className={`seg ${b.number === block?.number ? 'is-on' : ''} ${
                                  bad ? 'is-broken' : ''
                                } seg--${current === 'model-channel' ? 'model' : 'docs'}`}
                                onClick={() => setSelected(b.number)}
                                aria-label={`Block ${b.number}`}
                              >
                                <span className="seg__weft" aria-hidden="true">
                                  {Array.from({ length: 6 }, (_, i) => <span key={i} />)}
                                </span>
                                <span className="mono seg__n">
                                  {b.number.toString().slice(-3)}
                                </span>
                              </button>
                            </li>
                          );
                        })}
                      </ol>
                    </div>

                    <div className="led__paging">
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        disabled={offset === 0}
                        onClick={() => { setOffset((o) => Math.max(0, o - WINDOW)); setSelected(null); }}
                      >
                        newer
                      </button>
                      <span className="small dim">
                        blocks {commas(Math.max(0, height - offset - page.length) + 1)}–
                        {commas(height - offset)} of {commas(height)}
                      </span>
                      <button
                        type="button"
                        className="btn btn--ghost btn--sm"
                        disabled={offset + WINDOW >= height}
                        onClick={() => { setOffset((o) => o + WINDOW); setSelected(null); }}
                      >
                        older
                      </button>
                    </div>

                    <p className="small led__legend">
                      <span className="key key--docs" /> document channel
                      <span className="key key--model" /> model channel
                      <span className="key key--broken" /> contains an invalidated transaction
                    </p>

                    {block && (
                      <section className="blockcard">
                        <div className="blockcard__head">
                          <h2 className="mono blockcard__n">block #{commas(block.number)}</h2>
                          <Seal tone={block.transactions.every((t) => t.valid) ? 'sealed' : 'broken'}>
                            {block.transactions.every((t) => t.valid) ? 'all valid' : 'contains invalid'}
                          </Seal>
                        </div>

                        <div className="blockcard__grid">
                          <div>
                            <LedgerRow label="Channel"><span className="mono">{current}</span></LedgerRow>
                            <LedgerRow label="Timestamp">{dateTime(block.timestamp)}</LedgerRow>
                            <LedgerRow label="Proposer"><span className="mono">{block.proposer}</span></LedgerRow>
                            <LedgerRow label="Block hash"><HashChip value={block.block_hash} /></LedgerRow>
                            <LedgerRow label="Previous"><HashChip value={block.previous_hash} /></LedgerRow>
                            <LedgerRow label="Data hash"><HashChip value={block.data_hash} /></LedgerRow>
                          </div>

                          <div>
                            <p className="stamp-type blockcard__label">
                              Transactions ({block.transaction_count})
                            </p>
                            {block.transactions.length === 0 && (
                              <p className="small dim">
                                A configuration block. It carries the channel definition
                                rather than a transaction.
                              </p>
                            )}
                            {block.transactions.map((t) => (
                              <div key={t.tx_id} className={`tx ${t.valid ? '' : 'is-bad'}`}>
                                <div className="tx__top">
                                  <span className="mono tx__cc">{t.chaincode}</span>
                                  <span className="tx__fn">{t.function.replace(/_/g, ' ')}</span>
                                  <span className={`tx__code stamp-type ${t.valid ? 'ok' : 'bad'}`}>
                                    {t.validation}
                                  </span>
                                </div>
                                <p className="small tx__sub">
                                  submitted by <span className="mono">{t.submitter}</span>
                                </p>
                                <p className="small tx__end">endorsed by {t.endorsers.join(', ')}</p>
                                <HashChip value={t.tx_id} />
                                {t.writes.length > 0 && (
                                  <p className="small tx__end">
                                    wrote <span className="mono">{t.writes.slice(0, 3).join(', ')}</span>
                                    {t.writes.length > 3 && ` +${t.writes.length - 3} more`}
                                  </p>
                                )}
                                {!t.valid && (
                                  <p className="small tx__why">
                                    Kept in the block rather than dropped. The ledger records
                                    what was attempted, not only what succeeded.
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      </section>
                    )}
                  </>
                );
              }}
            </Result>
          </>
        )}
      </Result>
    </div>
  );
}
