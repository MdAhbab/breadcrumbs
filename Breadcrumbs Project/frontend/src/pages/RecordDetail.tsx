import { ArrowLeft } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { ThreeChecks } from '../components/ThreeChecks';
import { Disclosure, HashChip, LedgerRow, Seal } from '../components/ui';
import { WitnessPanel } from '../components/WitnessPanel';
import { VERIFICATIONS, WITNESS } from '../lib/anchor';
import { BOLTS, GRANTS, PURPOSE_CODES, RECORD_LABEL, VERIFICATION, orgName } from '../lib/data';
import { commas, dateTime, longDate, period } from '../lib/format';
import './record.css';

/** One bolt: its history, who may read a thread of it, and who has. */
export default function RecordDetail() {
  const { id } = useParams();
  const bolt = BOLTS.find((b) => b.recordId === id) ?? BOLTS[0];
  const grants = GRANTS.filter((g) => g.recordId === bolt.recordId);

  return (
    <div className="rec">
      <Link to="/factory/dashboard" className="rec__back">
        <ArrowLeft size={14} /> Loom floor
      </Link>

      <header className="rec__head">
        <div>
          <p className="stamp-type rec__eyebrow">
            {bolt.recordId} · {bolt.site}
          </p>
          <h1>{RECORD_LABEL[bolt.recordType]}</h1>
          <p className="lead rec__lede">{period(bolt.period)} · Apex Textile Ltd</p>
        </div>
        <Seal tone={bolt.status === 'committed' ? 'sealed' : 'inert'}>
          {bolt.status === 'committed' ? 'Sealed' : 'Superseded'}
        </Seal>
      </header>

      <div className="rec__figures">
        <Fig n={commas(bolt.rowCount)} l="threads woven" />
        <Fig n={`#${commas(bolt.block)}`} l="sealed in block" />
        <Fig n={bolt.schemaVersion} l="schema" />
        <Fig n={longDate(bolt.committedAt)} l="sealed on" />
      </div>

      <div className="rec__body">
        <section>
          <h2 className="rec__h2">History</h2>
          <ol className="tl">
            <li className="tl__item">
              <span className="tl__dot" />
              <div>
                <p className="tl__what">Record sealed to the ledger</p>
                <p className="small tl__when">
                  {dateTime(bolt.committedAt)} · {commas(bolt.rowCount)} threads
                </p>
                <HashChip value={bolt.merkleRoot} />
              </div>
            </li>
            {grants.filter((g) => g.status !== 'pending').map((g) => (
              <li key={g.grantId} className="tl__item">
                <span className={`tl__dot ${g.status === 'revoked' ? 'is-bad' : ''}`} />
                <div>
                  <p className="tl__what">
                    {g.status === 'revoked' ? 'Access revoked from' : 'Access granted to'}{' '}
                    {orgName(g.requesterMsp)}
                  </p>
                  <p className="small tl__when">
                    {g.status === 'revoked' ? g.revokedReason : `${PURPOSE_CODES[g.purposeCode]} · one field, until ${longDate(g.expiresAt)}`}
                  </p>
                </div>
              </li>
            ))}
            <li className="tl__item">
              <span className="tl__dot is-ok" />
              <div>
                <p className="tl__what">Verification completed</p>
                <p className="small tl__when">
                  {dateTime(VERIFICATION.verifiedAt)} · one thread proved against the root
                </p>
                <Link to="/verify/vr-001" className="tl__link">See the receipt</Link>
              </div>
            </li>
          </ol>

          <h2 className="rec__h2 rec__h2--spaced">Counter-signature</h2>
          <WitnessPanel req={WITNESS[bolt.recordId] ?? WITNESS['rc-002']} />

          <h2 className="rec__h2 rec__h2--spaced">Anchored in the accumulator</h2>
          <ThreeChecks result={VERIFICATIONS[bolt.recordId] ?? VERIFICATIONS['rc-001']} />

          <Disclosure summary="Technical detail">
            <LedgerRow label="Merkle root"><HashChip value={bolt.merkleRoot} /></LedgerRow>
            <LedgerRow label="Channel"><span className="mono">documents-apex-primark</span></LedgerRow>
            <LedgerRow label="Chaincode"><span className="mono">doccustody</span></LedgerRow>
            <LedgerRow label="Endorsed by">ApexTextileMSP, BVCertificationMSP</LedgerRow>
            <LedgerRow label="Salt policy">Per-row, 128-bit, released only with a proof</LedgerRow>
            <LedgerRow label="Storage">Encrypted, on the factory's own storage</LedgerRow>
          </Disclosure>
        </section>

        <aside>
          <h2 className="rec__h2">Who may read a thread</h2>
          {grants.length === 0 ? (
            <p className="small rec__none">Nobody yet. This record is sealed but unshared.</p>
          ) : (
            <ul className="grants">
              {grants.map((g) => (
                <li key={g.grantId} className={`grant is-${g.status}`}>
                  <div className="grant__top">
                    <span className="grant__org">{orgName(g.requesterMsp)}</span>
                    <Seal
                      tone={
                        g.status === 'active' ? 'sealed'
                          : g.status === 'pending' ? 'pending'
                            : g.status === 'revoked' ? 'broken' : 'inert'
                      }
                    >
                      {g.status}
                    </Seal>
                  </div>
                  <p className="mono grant__field">{g.fieldName}</p>
                  <p className="small grant__meta">
                    {PURPOSE_CODES[g.purposeCode]} · until {longDate(g.expiresAt)}
                  </p>
                  {g.status === 'active' && (
                    <button type="button" className="btn btn--danger btn--sm grant__revoke">
                      Revoke
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <p className="small rec__note">
            A grant covers exactly one field. Anything outside it is refused by the
            contract, so a wider request cannot be honoured by mistake.
          </p>
        </aside>
      </div>
    </div>
  );
}

function Fig({ n, l }: { n: string; l: string }) {
  return (
    <div className="rfig">
      <span className="rfig__n">{n}</span>
      <span className="small rfig__l">{l}</span>
    </div>
  );
}
