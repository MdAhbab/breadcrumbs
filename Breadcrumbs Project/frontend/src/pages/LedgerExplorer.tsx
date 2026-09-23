import { ShieldAlert, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

import { Result } from '../components/states';
import { Tech } from '../components/Tech';
import { HashChip, LedgerRow, Seal } from '../components/ui';
import { api, functionLabel, shortMsp, type Block, type Channel } from '../lib/api';
import { useDetail } from '../lib/detail';
import { commas, dateTime } from '../lib/format';
import { channelLabel } from '../lib/plainReason';
import { useApi } from '../lib/useApi';
import './ledger.css';

const WINDOW = 60;

/** The shared action label, as the start of a sentence. */
const plainFunction = (fn: string): string => {
  const label = functionLabel(fn);
  return label.charAt(0).toUpperCase() + label.slice(1);
};

/**
 * Transaction history: the ledger as a strip of entries.
 *
 * Each entry is a segment, its part of the ledger decides its colour, and a
 * refused action shows as a broken thread rather than a red row in a table.
 *
 * The "nothing has been altered" claim at the top is the result of
 * `/api/ledger/verify`, which re-hashes every block on every channel.
 */
export default function LedgerExplorer() {
  const { technical } = useDetail();
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
      <Result query={chain} pendingLabel="Checking every entry">
        {(integrity) => (
          <>
            <header className="led__head">
              <div>
                <p className="stamp-type led__eyebrow">
                  {commas(integrity.channels.reduce((a, c) => a + c.height, 0))} entries
                </p>
                {/* The name on the navigation, not a second one for the same screen. */}
                <h1>Transaction history</h1>
                <p className="lead led__lede">
                  Everything written to the ledger, newest first. Pick an entry on the
                  strip to see what it holds.
                </p>
              </div>
              <div className={`led__integrity ${integrity.ok ? '' : 'is-bad'}`}>
                {integrity.ok ? <ShieldCheck size={16} /> : <ShieldAlert size={16} />}
                <div>
                  <p className="led__int-head">
                    {integrity.ok ? 'Nothing has been altered' : 'Something has been altered'}
                  </p>
                  <p className="small led__int-body">
                    {integrity.ok
                      ? 'Every entry was checked just now. None has changed since it was written.'
                      : integrity.channels
                        .filter((c) => !c.integrity_ok)
                        .map((c) => `${channelLabel(c.channel)}: ${c.integrity_detail}`)
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
                  {technical ? c.channel : channelLabel(c.channel)} · {commas(c.height)}
                </button>
              ))}
            </div>

            <Result query={blocks} pendingLabel="Reading entries">
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
                                aria-label={`Entry ${commas(b.number)}`}
                              >
                                <span className="seg__weft" aria-hidden="true">
                                  {Array.from({ length: 6 }, (_, i) => <span key={i} />)}
                                </span>
                                <span className="mono seg__n">{commas(b.number)}</span>
                              </button>
                            </li>
                          );
                        })}
                      </ol>
                    </div>

                    <div className="led__paging">
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        disabled={offset === 0}
                        onClick={() => { setOffset((o) => Math.max(0, o - WINDOW)); setSelected(null); }}
                      >
                        ← Newer
                      </button>
                      {/* The same numbers the strip and the entry heading show. */}
                      {page.length > 0 && (
                        <span className="small dim">
                          Entries {commas(page[page.length - 1].number)}–
                          {commas(page[0].number)} of {commas(height)}
                        </span>
                      )}
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        disabled={offset + WINDOW >= height}
                        onClick={() => { setOffset((o) => o + WINDOW); setSelected(null); }}
                      >
                        Older →
                      </button>
                    </div>

                    <p className="small led__legend">
                      <span className="key key--docs" /> about a document
                      <span className="key key--model" /> about the AI model
                      <span className="key key--broken" /> holds something that was refused
                    </p>

                    {block && (
                      <section className="blockcard">
                        <div className="blockcard__head">
                          <h2 className="blockcard__n">Entry {commas(block.number)}</h2>
                          <Seal tone={block.transactions.every((t) => t.valid) ? 'sealed' : 'broken'}>
                            {block.transactions.every((t) => t.valid) ? 'Accepted' : 'Holds a refusal'}
                          </Seal>
                        </div>

                        <div className="blockcard__grid">
                          <div>
                            <LedgerRow label="Written">{dateTime(block.timestamp)}</LedgerRow>
                            <LedgerRow label="Part of the ledger">
                              {current ? channelLabel(current) : ''}
                            </LedgerRow>
                            <Tech>
                              <LedgerRow label="Proposer">
                                <span className="mono">{block.proposer}</span>
                              </LedgerRow>
                              <LedgerRow label="Channel"><span className="mono">{current}</span></LedgerRow>
                              <LedgerRow label="Block hash"><HashChip value={block.block_hash} /></LedgerRow>
                              <LedgerRow label="Previous"><HashChip value={block.previous_hash} /></LedgerRow>
                              <LedgerRow label="Data hash"><HashChip value={block.data_hash} /></LedgerRow>
                            </Tech>
                          </div>

                          <div>
                            <p className="stamp-type blockcard__label">
                              What was written ({commas(block.transaction_count)})
                            </p>
                            {block.transactions.length === 0 && (
                              <p className="small dim">
                                A setup entry. It holds the network&rsquo;s own settings.
                              </p>
                            )}
                            {block.transactions.map((t) => (
                              <div key={t.tx_id} className={`tx ${t.valid ? '' : 'is-bad'}`}>
                                <div className="tx__top">
                                  <Tech><span className="mono tx__cc">{t.chaincode}</span></Tech>
                                  <span className="tx__fn">
                                    {technical ? t.function.replace(/_/g, ' ') : plainFunction(t.function)}
                                  </span>
                                  <span className={`tx__code stamp-type ${t.valid ? 'ok' : 'bad'}`}>
                                    {technical ? t.validation : t.valid ? 'Accepted' : 'Refused'}
                                  </span>
                                </div>
                                <p className="small tx__sub">
                                  by{' '}
                                  {technical
                                    ? <span className="mono">{t.submitter}</span>
                                    : shortMsp(t.submitter.split('::')[0])}
                                </p>
                                <p className="small tx__end">
                                  approved by{' '}
                                  {technical
                                    ? t.endorsers.join(', ')
                                    : t.endorsers.map(shortMsp).join(', ')}
                                </p>
                                <Tech>
                                  <HashChip value={t.tx_id} />
                                  {t.writes.length > 0 && (
                                    <p className="small tx__end">
                                      wrote <span className="mono">{t.writes.slice(0, 3).join(', ')}</span>
                                      {t.writes.length > 3 && ` +${t.writes.length - 3} more`}
                                    </p>
                                  )}
                                </Tech>
                                {!t.valid && (
                                  <p className="small tx__why">
                                    Refused, and kept anyway. Failed attempts stay on the
                                    ledger too.
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
