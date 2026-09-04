import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { Empty, Result } from '../components/states';
import { Tech } from '../components/Tech';
import { HashChip, Seal } from '../components/ui';
import { api, recordLabel, type LedgerRecord } from '../lib/api';
import { commas, longDate, period } from '../lib/format';
import { useSession } from '../lib/session';
import { useApi } from '../lib/useApi';
import './records.css';

const PAGE = 40;

/**
 * Every record this caller may see, filterable.
 *
 * The overview shows the newest dozen; this is all of them. It exists
 * because the ledger now holds hundreds of documents rather than the five a
 * fixture file could hold, and a dashboard that silently truncates is a
 * dashboard that lies about how much there is.
 *
 * The filters are built from the data rather than from a list of the record
 * types someone remembered — a period or a site that appears here appears
 * because the ledger has one.
 */
export default function Records() {
  const { role } = useSession();
  const auditor = role?.id === 'auditor';
  const records = useApi(() => api.records(), []);
  const [type, setType] = useState('');
  const [site, setSite] = useState('');
  const [per, setPer] = useState('');
  const [query, setQuery] = useState('');
  const [shown, setShown] = useState(PAGE);

  return (
    <div className="recs">
      <Result query={records} pendingLabel="Listing what you may see">
        {(all) => {
          const facets = {
            types: [...new Set(all.map((r) => r.record_type))].sort(),
            sites: [...new Set(all.map((r) => r.site))].sort(),
            periods: [...new Set(all.map((r) => r.period))].sort().reverse(),
          };
          // eslint-disable-next-line react-hooks/rules-of-hooks
          const filtered = all.filter(
            (r) =>
              (!type || r.record_type === type)
              && (!site || r.site === site)
              && (!per || r.period === per)
              && (!query || r.record_id.toLowerCase().includes(query.toLowerCase())),
          );

          return (
            <>
              <header className="recs__head">
                <div>
                  <p className="stamp-type recs__eyebrow">Published to the ledger</p>
                  <h1>{auditor ? 'All documents' : 'Records'}</h1>
                  <p className="lead recs__lede">
                    {commas(filtered.length)} of {commas(all.length)}. Each one is a document
                    that never moved. Only a fingerprint of it is on the ledger.
                    {auditor && ' As an auditor you can open any of them without asking.'}
                  </p>
                </div>
              </header>

              <div className="recs__filters">
                <Pick label="Type" value={type} onChange={setType} options={facets.types} render={recordLabel} />
                <Pick label="Site" value={site} onChange={setSite} options={facets.sites} />
                <Pick label="Period" value={per} onChange={setPer} options={facets.periods} render={period} />
                <label className="recs__search">
                  <span className="stamp-type">Search by name</span>
                  <input
                    className="input"
                    type="search"
                    value={query}
                    placeholder="doc-…"
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </label>
              </div>

              {filtered.length === 0 ? (
                <Empty
                  title="Nothing matches"
                  detail="No record on the ledger fits those filters. Widen one of them."
                />
              ) : (
                <>
                  <div className="scroll-x">
                    <table className="recstable">
                      <thead>
                        <tr>
                          <th scope="col">Record</th>
                          <th scope="col">Type</th>
                          <th scope="col">Period</th>
                          <th scope="col">Site</th>
                          <th scope="col">Rows</th>
                          <th scope="col">Counter-signed</th>
                          <Tech><th scope="col">Root</th></Tech>
                          <th scope="col">Published</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filtered.slice(0, shown).map((r) => (
                          <Row key={r.record_id} r={r} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {shown < filtered.length && (
                    <button
                      type="button"
                      className="btn btn--ghost recs__more"
                      onClick={() => setShown((n) => n + PAGE)}
                    >
                      Show {Math.min(PAGE, filtered.length - shown)} more
                    </button>
                  )}
                </>
              )}
            </>
          );
        }}
      </Result>
    </div>
  );
}

function Row({ r }: { r: LedgerRecord }) {
  return (
    <tr className={r.status === 'superseded' ? 'is-superseded' : ''}>
      <th scope="row">
        <Link to={`/factory/records/${encodeURIComponent(r.record_id)}`} className="mono">
          {r.record_id}
        </Link>
      </th>
      <td>{recordLabel(r.record_type)}</td>
      <td>{period(r.period)}</td>
      <td>{r.site}</td>
      <td className="mono num">{commas(r.row_count)}</td>
      <td>
        {r.witnesses.length > 0 ? (
          <Seal tone="sealed">yes</Seal>
        ) : (
          <span className="small dim">not sampled</span>
        )}
      </td>
      <Tech><td><HashChip value={r.merkle_root} /></td></Tech>
      <td className="mono dim">{longDate(r.committed_at)}</td>
    </tr>
  );
}

function Pick({
  label, value, onChange, options, render,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  render?: (v: string) => string;
}) {
  const id = useMemo(() => `pick-${label.toLowerCase()}`, [label]);
  return (
    <label className="recs__pick" htmlFor={id}>
      <span className="stamp-type">{label}</span>
      <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>{render ? render(o) : o}</option>
        ))}
      </select>
    </label>
  );
}
