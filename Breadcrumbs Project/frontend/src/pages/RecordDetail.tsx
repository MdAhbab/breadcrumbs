import { ArrowLeft } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { DocumentCheck } from '../components/DocumentCheck';
import { Screening } from '../components/Screening';
import { Failed, Result } from '../components/states';
import { ThreeChecks } from '../components/ThreeChecks';
import { Tech } from '../components/Tech';
import { Disclosure, HashChip, LedgerRow, Seal } from '../components/ui';
import { WitnessPanel } from '../components/WitnessPanel';
import {
  ApiError, api, purposeLabel, recordLabel, shortMsp,
  type Grant, type RecordDetail as Detail,
} from '../lib/api';
import { commas, dateTime, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import { useFieldLabel } from '../lib/useFieldLabel';
import './record.css';

/** One record: what is in it, what has happened to it, and who may read it. */
export default function RecordDetail() {
  const { id = '' } = useParams();
  const { role } = useSession();
  const fieldLabel = useFieldLabel();
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
      {/* The factory has a record list to go back to; everybody else goes to
          their own workspace. Sending an auditor or a regulator to the buyer's
          portal is the same bug as the one on /verify, one page over. */}
      <Link
        to={role?.id === 'factory' ? '/factory/records' : role?.landing ?? '/'}
        className="rec__back"
      >
        <ArrowLeft size={14} /> Back
      </Link>

      <Result query={main} pendingLabel="Reading the record off the chain">
        {([detail, allGrants]) => {
          const b = detail.record;
          const grants = allGrants.filter((g) => g.record_id === b.record_id);
          const labelOf = (field: string) => fieldLabel(b.record_type, field);

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
                  {b.status === 'committed' ? 'Published' : 'Corrected'}
                </Seal>
              </header>

              <div className="rec__figures">
                <Fig n={commas(b.row_count)} l="rows in the file" />
                <Fig n={longDate(b.committed_at)} l="published on" />
                <Fig n="0" l="rows the ledger can read" />
                <Tech><Fig n={b.schema_version} l="schema" /></Tech>
              </div>

              <div className="rec__body">
                <section>
                  {/* Ahead of the history, because "what is this document?" is
                      the question a reader arrives with, and the page used to
                      answer every question except that one. */}
                  <DocumentCheck recordId={b.record_id} />

                  <h2 className="rec__h2 rec__h2--spaced">History</h2>
                  <ol className="tl">
                    <li className="tl__item">
                      <span className="tl__dot" />
                      <div>
                        <p className="tl__what">Published to the ledger</p>
                        <p className="small tl__when">
                          {dateTime(b.committed_at)} · {commas(b.row_count)} rows
                          <Tech> · published by {b.committed_by}</Tech>
                        </p>
                        <Tech><HashChip value={b.merkle_root} /></Tech>
                      </div>
                    </li>

                    {grants.map((g) => (
                      <li key={g.grant_id} className="tl__item">
                        <span className={`tl__dot ${g.status === 'revoked' ? 'is-bad' : ''}`} />
                        <div>
                          <p className="tl__what">
                            {g.status === 'revoked' ? 'Access withdrawn from' : 'Access given to'}{' '}
                            {shortMsp(g.requester_msp)}
                          </p>
                          <p className="small tl__when">
                            {g.status === 'revoked'
                              ? g.revoked_reason
                              : `${purposeLabel(g.purpose_code)} · one column, until ${longDate(g.expires_at)}`}
                          </p>
                        </div>
                      </li>
                    ))}

                    {detail.receipts.map((r) => (
                      <li key={r.receipt_id} className="tl__item">
                        <span className={`tl__dot ${r.result === 'match' ? 'is-ok' : 'is-bad'}`} />
                        <div>
                          <p className="tl__what">
                            {r.result === 'match' ? 'Checked and matched' : 'Check failed'}
                          </p>
                          <p className="small tl__when">
                            {dateTime(r.verified_at)} · {shortMsp(r.verifier_msp)} checked{' '}
                            <strong>{labelOf(r.field_name)}</strong> against the published
                            fingerprint
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
                          <p className="tl__what">Corrected by a later version</p>
                          <p className="small tl__when">
                            This version is not deleted, and it stays checkable.
                          </p>
                        </div>
                      </li>
                    )}
                  </ol>

                  <h2 className="rec__h2 rec__h2--spaced">Who counter-signed it</h2>
                  <Result query={witness} pendingLabel="Asking who was assigned">
                    {(req) => <WitnessPanel req={req} />}
                  </Result>

                  <h2 className="rec__h2 rec__h2--spaced">Has it been tampered with?</h2>
                  <Result query={anchored} pendingLabel="Running the checks">
                    {(result) => <ThreeChecks result={result} />}
                  </Result>

                  <h2 className="rec__h2 rec__h2--spaced">What the detector thinks</h2>
                  <p className="small rec__note">
                    Everything above this line is proof: anyone can check it, and it
                    settles the question. Everything below it is a guess. Keeping the two
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
                  <h2 className="rec__h2">Who can read part of this</h2>
                  {grants.length === 0 ? (
                    <p className="small rec__none">
                      Nobody yet. It is published, and shared with no one.
                    </p>
                  ) : (
                    <ul className="grants">
                      {grants.map((g) => (
                        <GrantRow
                          key={g.grant_id}
                          grant={g}
                          label={labelOf(g.field_name)}
                          canRevoke={role?.id === 'factory' && g.status === 'active'}
                          onChange={main.reload}
                        />
                      ))}
                    </ul>
                  )}
                  <p className="small rec__note">
                    Access covers exactly one column. Anything wider is refused by the
                    contract itself, so it cannot be given away by mistake.
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

/**
 * One grant, and the one irreversible thing this page can do to it.
 *
 * Revoking used to be a single unguarded click that wrote the fixed string
 * "Revoked by the record owner from the record view" — which records the screen
 * the button was on rather than why access was ended. That string goes onto the
 * ledger permanently, under the identity that pressed it, and is shown to the
 * organisation whose access it ends. So it asks, and it asks before rather than
 * after.
 */
function GrantRow({
  grant, label, canRevoke, onChange,
}: {
  grant: Grant;
  label: string;
  canRevoke: boolean;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState('');
  const [failure, setFailure] = useState<ApiError | null>(null);

  const revoke = async () => {
    setBusy(true);
    setFailure(null);
    try {
      await api.revoke(grant.grant_id, reason.trim());
      setAsking(false);
      setReason('');
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
      <p className="grant__field">{label}</p>
      <p className="small grant__meta">
        {purposeLabel(grant.purpose_code)} · until {longDate(grant.expires_at)}
      </p>
      {grant.revoked_reason && <p className="small grant__meta">{grant.revoked_reason}</p>}
      {failure && <Failed error={failure} />}
      {canRevoke && (asking ? (
        <div className="grant__ask">
          <input
            className="input"
            placeholder="Why is this being withdrawn?"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            autoFocus
          />
          <p className="small grant__asknote">
            Permanent, and written to the ledger under your name. You can give access
            again afterwards; it will be a new, separate permission.
          </p>
          <div className="grant__askrow">
            <button
              type="button"
              className="btn btn--danger btn--sm"
              onClick={() => void revoke()}
              disabled={busy || reason.trim().length < 4}
            >
              {busy ? 'Withdrawing…' : 'Withdraw, permanently'}
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => { setAsking(false); setReason(''); }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="btn btn--danger btn--sm grant__revoke"
          onClick={() => setAsking(true)}
        >
          Withdraw access
        </button>
      ))}
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
