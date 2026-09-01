import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { BOLTS, GRANTS, MOTIONS, ORGS, RECORD_LABEL, type Org } from '../lib/data';
import { commas, longDate, shortHash } from '../lib/format';
import { useReducedMotion } from '../lib/useMotionPref';
import { Modal, ModalHead, Seal } from './ui';
import './mesh.css';

/**
 * The network, from above.
 *
 * The consortium administrator is the only role that sees every organisation at
 * once, so this is the one view in the product that is a graph rather than a
 * list. BGMEA sits at the centre because it is the only member on every channel;
 * everyone else is placed by kind, and the edges are the channels they actually
 * share.
 *
 * Selecting a node opens its record as a short sequence of blocks, advanced one
 * at a time. That form suits the content: a member's standing is a handful of
 * discrete facts, not a page of prose, and reading them in order is how you
 * would be briefed on a counterparty.
 */

interface Node extends Org {
  x: number;
  y: number;
  ring: 0 | 1;
}

const KIND_ORDER = ['factory', 'buyer', 'auditor', 'regulator'] as const;

function layout(): Node[] {
  const centre = ORGS.find((o) => o.kind === 'consortium')!;
  const outer = ORGS.filter((o) => o.kind !== 'consortium').sort(
    (a, b) =>
      KIND_ORDER.indexOf(a.kind as (typeof KIND_ORDER)[number]) -
      KIND_ORDER.indexOf(b.kind as (typeof KIND_ORDER)[number]),
  );

  const nodes: Node[] = [{ ...centre, x: 50, y: 50, ring: 0 }];
  outer.forEach((o, i) => {
    // Start at the top and go clockwise, so the reading order matches the legend.
    const angle = (i / outer.length) * Math.PI * 2 - Math.PI / 2;
    nodes.push({
      ...o,
      x: 50 + Math.cos(angle) * 33,
      y: 50 + Math.sin(angle) * 33,
      ring: 1,
    });
  });
  return nodes;
}

/** What a member is doing on the network, as a handful of discrete facts. */
function storyFor(org: Org) {
  const owned = BOLTS.filter((b) => b.ownerMsp === org.mspId);
  const asRequester = GRANTS.filter((g) => g.requesterMsp === org.mspId);
  const endorsed = MOTIONS.filter((m) => m.endorsers.includes(org.mspId));

  return [
    {
      label: 'Standing',
      body: (
        <>
          <p className="story__lede">
            {org.name} joined the consortium on {longDate(org.joined)} and holds a{' '}
            {org.kind} identity on the network.
          </p>
          <div className="story__rows">
            <Row k="MSP identity" v={<span className="mono">{org.mspId}</span>} />
            <Row k="Country" v={org.country} />
            <Row k="Status" v={<Seal tone="sealed">in good standing</Seal>} />
          </div>
        </>
      ),
    },
    {
      label: org.kind === 'factory' ? 'Records sealed' : 'Records reached',
      body:
        org.kind === 'factory' ? (
          owned.length ? (
            <>
              <p className="story__lede">
                {owned.length} bolts sealed, {commas(owned.reduce((a, b) => a + b.rowCount, 0))}{' '}
                threads in total.
              </p>
              <div className="story__rows">
                {owned.slice(0, 4).map((b) => (
                  <Row
                    key={b.recordId}
                    k={RECORD_LABEL[b.recordType]}
                    v={<span className="mono">{shortHash(b.merkleRoot)}</span>}
                  />
                ))}
              </div>
            </>
          ) : (
            <p className="story__lede">
              No records sealed yet. This member has an identity but has not committed.
            </p>
          )
        ) : (
          <>
            <p className="story__lede">
              {asRequester.length
                ? `${asRequester.length} grants held or requested. Each covers exactly one field.`
                : 'Holds no access grants. This member observes the network only.'}
            </p>
            <div className="story__rows">
              {asRequester.slice(0, 4).map((g) => (
                <Row key={g.grantId} k={g.fieldName} v={g.status} />
              ))}
            </div>
          </>
        ),
    },
    {
      label: 'Governance',
      body: (
        <>
          <p className="story__lede">
            {endorsed.length
              ? `Has affixed a seal to ${endorsed.length} motion${endorsed.length === 1 ? '' : 's'} of the chamber.`
              : 'Has not endorsed a motion in the current session.'}
          </p>
          <div className="story__rows">
            {endorsed.map((m) => (
              <Row key={m.id} k={m.caseNo} v={m.title.slice(0, 44) + (m.title.length > 44 ? '…' : '')} />
            ))}
          </div>
        </>
      ),
    },
  ];
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="story__row">
      <span className="stamp-type story__k">{k}</span>
      <span className="story__v">{v}</span>
    </div>
  );
}

export function ConsortiumMesh() {
  const nodes = useMemo(layout, []);
  const [open, setOpen] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const reduced = useReducedMotion();

  const selected = nodes.find((n) => n.mspId === open) ?? null;
  const centre = nodes[0];

  return (
    <div className="mesh">
      <div className="mesh__stage">
        <svg className="mesh__svg" viewBox="0 0 100 100" role="img"
          aria-label="Consortium network. Seven organisations connected by shared channels.">
          {/* Concentric guides — the network has a shape, and it is not accidental. */}
          <circle cx="50" cy="50" r="33" className="mesh__guide" />
          <circle cx="50" cy="50" r="16.5" className="mesh__guide mesh__guide--faint" />

          {nodes.slice(1).map((n) => {
            const lit = hover === n.mspId || open === n.mspId;
            return (
              <line
                key={n.mspId}
                x1={centre.x} y1={centre.y} x2={n.x} y2={n.y}
                className={`mesh__edge ${lit ? 'is-lit' : ''}`}
              />
            );
          })}

          {/* The document channel: a direct link between the factory and its buyer. */}
          <line
            x1={nodes.find((n) => n.mspId === 'ApexTextileMSP')!.x}
            y1={nodes.find((n) => n.mspId === 'ApexTextileMSP')!.y}
            x2={nodes.find((n) => n.mspId === 'PrimarkSourcingMSP')!.x}
            y2={nodes.find((n) => n.mspId === 'PrimarkSourcingMSP')!.y}
            className="mesh__edge mesh__edge--doc"
          />

          {nodes.map((n) => {
            const lit = hover === n.mspId || open === n.mspId;
            return (
              <g
                key={n.mspId}
                className={`mesh__node mesh__node--${n.kind} ${lit ? 'is-lit' : ''}`}
                transform={`translate(${n.x} ${n.y})`}
                onMouseEnter={() => setHover(n.mspId)}
                onMouseLeave={() => setHover(null)}
                onClick={() => setOpen(n.mspId)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(n.mspId); }
                }}
                tabIndex={0}
                role="button"
                aria-label={`${n.name}, ${n.kind}. Open record.`}
              >
                {!reduced && n.ring === 0 && <circle r="7.5" className="mesh__pulse" />}
                {/* A 4.6-unit disc is a 34px target at this viewBox; the hit
                    area is widened so a thumb can land on it. */}
                <circle r="9" className="mesh__hit" />
                <circle r={n.ring === 0 ? 6 : 4.6} className="mesh__disc" />
                <text y={n.ring === 0 ? 0.9 : 0.8} className="mesh__initials">
                  {n.name.split(' ').slice(0, 2).map((w) => w[0]).join('')}
                </text>
                <text y={n.ring === 0 ? 11.5 : 9.6} className="mesh__label">
                  {n.name.replace(' Ltd', '').replace('Dept. of Labour, Bangladesh', 'Dept. of Labour')}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mesh__side">
        <p className="stamp-type mesh__sidehead">The network from above</p>
        <p className="small mesh__note">
          BGMEA sits at the centre because it is the only member on every channel. Select
          an organisation to read its record.
        </p>
        <ul className="mesh__legend">
          {(['factory', 'buyer', 'auditor', 'regulator', 'consortium'] as const).map((k) => (
            <li key={k}>
              <span className={`swatch swatch--${k}`} /> {k}
            </li>
          ))}
        </ul>
        <ul className="mesh__list">
          {nodes.map((n) => (
            <li key={n.mspId}>
              <button
                type="button"
                className={`mesh__listbtn ${open === n.mspId ? 'is-on' : ''}`}
                onClick={() => setOpen(n.mspId)}
                onMouseEnter={() => setHover(n.mspId)}
                onMouseLeave={() => setHover(null)}
              >
                <span className={`swatch swatch--${n.kind}`} />
                {n.name}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {selected && <OrgStory org={selected} onClose={() => setOpen(null)} />}
    </div>
  );
}

/* ------------------------------------------------------------- the story --- */
function OrgStory({ org, onClose }: { org: Org; onClose: () => void }) {
  const blocks = useMemo(() => storyFor(org), [org]);
  const [i, setI] = useState(0);

  const next = useCallback(
    () => setI((v) => (v + 1 < blocks.length ? v + 1 : v)),
    [blocks.length],
  );
  const prev = useCallback(() => setI((v) => Math.max(0, v - 1)), []);

  useEffect(() => setI(0), [org.mspId]);

  // Advancing is the primary gesture, so it must work from the keyboard too.
  // Escape, Tab and the scroll lock belong to Modal.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') next();
      if (e.key === 'ArrowLeft') prev();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [next, prev]);

  const block = blocks[i];

  return (
    <Modal label={`${org.name} record`} onClose={onClose}>
      {/* Segmented progress: which block of how many. */}
      <div className="story__ticks">
        {blocks.map((b, n) => (
          <button
            key={b.label}
            type="button"
            className={`story__tick ${n <= i ? 'is-done' : ''}`}
            onClick={() => setI(n)}
            aria-label={`Block ${n + 1}: ${b.label}`}
          />
        ))}
      </div>

      <ModalHead eyebrow={`${org.kind} · ${org.country}`} title={org.name} onClose={onClose} />

      <div className="modal__body" key={i}>
        <p className="stamp-type story__label">{block.label}</p>
        {block.body}
      </div>

      <footer className="modal__foot">
        <button
          type="button"
          className="btn btn--onDark btn--sm"
          onClick={prev}
          disabled={i === 0}
        >
          <ChevronLeft size={14} /> Back
        </button>
        <span className="mono story__count">{i + 1} / {blocks.length}</span>
        <button
          type="button"
          className="btn btn--primary btn--sm"
          onClick={i + 1 < blocks.length ? next : onClose}
        >
          {i + 1 < blocks.length ? <>Next <ChevronRight size={14} /></> : 'Done'}
        </button>
      </footer>
    </Modal>
  );
}
