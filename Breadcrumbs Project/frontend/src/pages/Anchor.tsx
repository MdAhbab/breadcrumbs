import { EpochTimeline } from '../components/EpochTimeline';
import { PageHead } from '../components/ui';
import { ANCHOR_STATE } from '../lib/anchor';
import './periods.css';

/**
 * The accumulator: one integer that commits the whole record set.
 *
 * Consortium-wide facts, which is why the regulator can see this page while it
 * cannot see a single record, seal or grant. Nothing here names a document.
 */
export default function Anchor() {
  return (
    <div className="periods">
      <PageHead
        eyebrow="Accumulator · document channel"
        title="One number for the whole ledger"
        lede="Every committed record and every period seal is folded into a single 3072-bit integer. Checking one of them against it costs the same whether the set holds ten elements or ten million — 4.4ms either way, against 338ms to recompute a Merkle path."
      />
      <section className="periods__section">
        <EpochTimeline state={ANCHOR_STATE} />
      </section>
    </div>
  );
}
