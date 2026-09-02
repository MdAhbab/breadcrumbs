import { ArrowLeft } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { Screening } from '../components/Screening';
import { Failed, Result } from '../components/states';
import { ThreeChecks } from '../components/ThreeChecks';
import { Disclosure, HashChip, LedgerRow, Seal } from '../components/ui';
import { WitnessPanel } from '../components/WitnessPanel';
import {
  ApiError, api, recordLabel, shortMsp,
  type Grant, type RecordDetail as Detail,
} from '../lib/api';
import { commas, dateTime, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import './record.css';

/** One bolt: its history, who may read a thread of it, and who has. */
export default function RecordDetail() {
  const { id = '' } = useParams();
  const { role } = useSession();
  const main = useApi(
    () => Promise.all([api.record(id), api.grants()]) as Promise<[Detail, Grant[]]>,
    [id],
  );
  // Asked separately so a role without the capability loses one panel rather
  // than the whole page.
  const witness = useApi(() => api.witnessRequirement(id), [id]);
  const anchored = useApi(() => api.verifyRecord(id), [id]);

  return (
    <div className="rec">
      <Link to={role?.id === 'factory' ? '/factory/records' : '/buyer/portal'} className="rec__back">
        <ArrowLeft size={14} /> Back
      </Link>

      <Result query={main} pendingLabel="Reading the record off the chain">
        {([detail, allGrants]) => {
          const b = detail.record;
          const grants = allGrants.filter((g) => g.record_id === b.record_id);

          return (
            <>
              <header className="rec__head">
                <div>
                  <p className="stamp-type rec__eyebrow">{b.record_id} · {b.site}</p>
                  <h1>{recordLabel(b.record_type)}</h1>
                  <p className="lead rec__lede">
                    {period(b.period)} · {shortMsp(b.owner_msp)}
                  </p>
                </div>
                <Seal tone={b.status === 'committed' ? 'sealed' : 'inert'}>
                  {b.status === 'committed' ? 'Sealed' : 'Superseded'}
                </Seal>
              </header>

              <div className="rec__figures">
                <Fig n={commas(b.row_count)} l="threads woven" />
                <Fig n={commas(detail.rows_held_off_chain)} l="rows held off-chain" />
                <Fig n={b.schema_version} l="schema" />
                <Fig n={longDate(b.committed_at)} l="sealed on" />
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
                          {dateTime(b.committed_at)} · {commas(b.row_count)} threads ·
                          committed by {b.committed_by}
                        </p>
                        <HashChip value={b.merkle_root} />
                      </div>
                    </li>

                    {grants.map((g) => (
                      <li key={g.grant_id} className="tl__item">
                        <span className={`tl__dot ${g.status === 'revoked' ? 'is-bad' : ''}`} />
                        <div>
                          <p className="tl__what">
                            {g.status === 'revoked' ? 'Access revoked from' : 'Access granted to'}{' '}
                            {shortMsp(g.requester_msp)}
                          </p>
                          <p className="small tl__when">
                            {g.status === 'revoked'
                              ? g.revoked_reason
                              : `${g.purpose_code} · one field, until ${longDate(g.expires_at)}`}
                          </p>
                        </div>
                      </li>
                    ))}

                    {detail.receipts.map((r) => (
                      <li key={r.receipt_id} className="tl__item">
                        <span className={`tl__dot ${r.result === 'match' ? 'is-ok' : 'is-bad'}`} />
                        <div>
                          <p className="tl__what">
                            {r.result === 'match' ? 'Verification completed' : 'Verification failed'}
                          </p>
                          <p className="small tl__when">
                            {dateTime(r.verified_at)} · {shortMsp(r.verifier_msp)} proved{' '}
                            <span className="mono">{r.field_name}</span> against the root
                          </p>
                          <Link to={`/verify/${encodeURIComponent(r.receipt_id)}`} className="tl__link">
                            See the receipt
                          </Link>
                        </div>
                      </li>
                    ))}

                    {b.superseded_by && (
                      <li className="tl__item">
                        <span className="tl__dot is-bad" />
                        <div>
                          <p className="tl__what">Superseded by {b.superseded_by}</p>
                          <p className="small tl__when">
                            The old record is not deleted and its root stays verifiable.
                          </p>
                        </div>
                      </li>
                    )}
                  </ol>

                  <h2 className="rec__h2 rec__h2--spaced">Counter-signature</h2>
                  <Result query={witness} pendingLabel="Asking who was assigned">
                    {(req) => <WitnessPanel req={req} />}
                  </Result>

                  <h2 className="rec__h2 rec__h2--spaced">Anchored in the accumulator</h2>
                  <Result query={anchored} pendingLabel="Running the three checks">
                    {(result) => <ThreeChecks result={result} />}
                  </Result>

                  <h2 className="rec__h2 rec__h2--spaced">What the detector thinks</h2>
                  <p className="small rec__note">
                    Everything above this line is proof: it can be checked by anyone and it
                    settles the question. Everything below it is a guess. Keeping them
                    apart is the point of the heading.
                  </p>
                  <Screening recordId={b.record_id} />

                  <Disclosure summary="Technical detail">
                    <LedgerRow label="Record id"><span className="mono">{b.record_id}</span></LedgerRow>
                    <LedgerRow label="Merkle root"><HashChip value={b.merkle_root} /></LedgerRow>
                    <LedgerRow label="Bucket"><span className="mono">{b.bucket}</span></LedgerRow>
                    <LedgerRow label="Channel"><span className="mono">documents-apex-primark</span></LedgerRow>
                    <LedgerRow label="Chaincode"><span className="mono">doccustody</span></LedgerRow>
                    <LedgerRow label="Endorsement policy">
                      AND(ApexTextileMSP, BVCertificationMSP)
                    </LedgerRow>
                    <LedgerRow label="Salt policy">
                      Per-row, released only with a proof
                    </LedgerRow>
                    <LedgerRow label="Storage">
                      Off the chain. The API never serves a document body.
                    </LedgerRow>
                  </Disclosure>
                </section>

                <aside>
                  <h2 className="rec__h2">Who may read a thread</h2>
                  {grants.length === 0 ? (
                    <p className="small rec__none">
                      Nobody yet. This record is sealed but unshared.
                    </p>
                  ) : (
                    <ul className="grants">
                      {grants.map((g) => (
                        <GrantRow
                          key={g.grant_id}
                          grant={g}
                          canRevoke={role?.id === 'factory' && g.status === 'active'}
                          onChange={main.reload}
                        />
                      ))}
                    </ul>
                  )}
                  <p className="small rec__note">
                    A grant covers exactly one field. Anything outside it is refused by
                    the contract, so a wider request cannot be honoured by mistake.
                  </p>
                </aside>
              </div>
            </>
          );
        }}
      </Result>
    </div>
  );
}

function GrantRow({
  grant, canRevoke, onChange,
}: {
  grant: Grant;
  canRevoke: boolean;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<ApiError | null>(null);

  const revoke = async () => {
    setBusy(true);
    setFailure(null);
    try {
      await api.revoke(grant.grant_id, 'Revoked by the record owner from the bolt view');
      onChange();
    } catch (err) {
      setFailure(err instanceof ApiError ? err : new ApiError(0, 'the revocation failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={`grant is-${grant.status}`}>
      <div className="grant__top">
        <span className="grant__org">{shortMsp(grant.requester_msp)}</span>
        <Seal
          tone={
            grant.status === 'active' ? 'sealed'
              : grant.status === 'pending' ? 'pending'
                : grant.status === 'revoked' ? 'broken' : 'inert'
          }
        >
          {grant.status}
        </Seal>
      </div>
      <p className="mono grant__field">{grant.field_name}</p>
      <p className="small grant__meta">
        {grant.purpose_code} · until {longDate(grant.expires_at)}
      </p>
      {grant.revoked_reason && <p className="small grant__meta">{grant.revoked_reason}</p>}
      {failure && <Failed error={failure} />}
      {canRevoke && (
        <button
          type="button"
          className="btn btn--danger btn--sm grant__revoke"
          onClick={() => void revoke()}
          disabled={busy}
        >
          {busy ? 'Revoking…' : 'Revoke'}
        </button>
      )}
    </li>
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
