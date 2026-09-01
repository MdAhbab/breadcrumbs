/*
 * Domain types and the demo world.
 *
 * Every shape here mirrors what the Breadcrumbs API actually returns, so
 * swapping the mock for the live client is a one-line change in `api.ts`.
 * Accuracies arrive as integer basis points: 7790 means 77.90%.
 */

export type RoleId = 'factory' | 'buyer' | 'auditor' | 'consortium' | 'regulator';

export interface Role {
  id: RoleId;
  label: string;
  org: string;
  mspId: string;
  person: string;
  summary: string;
  landing: string;
  /** The layout grammar this role's dashboard uses. */
  instrument: string;
}

export const ROLES: Role[] = [
  {
    id: 'factory',
    label: 'Factory Compliance',
    org: 'Apex Textile Ltd',
    mspId: 'ApexTextileMSP',
    person: 'Fatema Begum',
    summary: 'Seal records, decide who may see which thread.',
    landing: '/factory/dashboard',
    instrument: 'The Loom Floor',
  },
  {
    id: 'buyer',
    label: 'Buyer / Brand',
    org: 'Primark Sourcing Ltd',
    mspId: 'PrimarkSourcingMSP',
    person: 'James Holloway',
    summary: 'Ask one narrow question. Receive one answer.',
    landing: '/buyer/portal',
    instrument: 'The Lightbox',
  },
  {
    id: 'auditor',
    label: 'Auditor',
    org: 'BV Certification',
    mspId: 'BVCertificationMSP',
    person: 'Dr. Meera Nair',
    summary: 'Verify in batches, then sign your name to it.',
    landing: '/auditor/workspace',
    instrument: 'The Bench',
  },
  {
    id: 'consortium',
    label: 'Consortium Administrator',
    org: 'BGMEA Consortium',
    mspId: 'BGMEAConsortiumMSP',
    person: 'Rafiqul Islam',
    summary: 'Motions, endorsements, membership, operations.',
    landing: '/governance',
    instrument: 'The Chamber',
  },
  {
    id: 'regulator',
    label: 'Regulator',
    org: 'Dept. of Labour, Bangladesh',
    mspId: 'DOLBangladeshMSP',
    person: 'Lt. Col. (Ret.) Aziz',
    summary: 'Aggregate statistics and governance events only.',
    landing: '/regulator',
    instrument: 'The Observatory',
  },
];

export const roleById = (id: RoleId): Role => ROLES.find((r) => r.id === id)!;

export interface Org {
  mspId: string;
  name: string;
  kind: 'factory' | 'buyer' | 'auditor' | 'consortium' | 'regulator';
  country: string;
  joined: string;
}

export const ORGS: Org[] = [
  { mspId: 'ApexTextileMSP', name: 'Apex Textile Ltd', kind: 'factory', country: 'Bangladesh', joined: '2026-01-14' },
  { mspId: 'NoorGarmentsMSP', name: 'Noor Garments Ltd', kind: 'factory', country: 'Bangladesh', joined: '2026-04-01' },
  { mspId: 'CrescentFashionMSP', name: 'Crescent Fashion Ltd', kind: 'factory', country: 'Bangladesh', joined: '2026-04-18' },
  { mspId: 'PrimarkSourcingMSP', name: 'Primark Sourcing Ltd', kind: 'buyer', country: 'Ireland', joined: '2026-02-02' },
  { mspId: 'BVCertificationMSP', name: 'BV Certification', kind: 'auditor', country: 'France', joined: '2026-03-15' },
  { mspId: 'BGMEAConsortiumMSP', name: 'BGMEA Consortium', kind: 'consortium', country: 'Bangladesh', joined: '2026-01-02' },
  { mspId: 'DOLBangladeshMSP', name: 'Dept. of Labour, Bangladesh', kind: 'regulator', country: 'Bangladesh', joined: '2026-01-02' },
];

export const orgName = (mspId: string) => ORGS.find((o) => o.mspId === mspId)?.name ?? mspId;

/* -- records: a "bolt" of cloth ------------------------------------------ */
export type RecordType =
  | 'payroll_register'
  | 'safety_inspection'
  | 'chemical_inventory'
  | 'machine_maintenance'
  | 'compliance_certificate';

export const RECORD_LABEL: Record<RecordType, string> = {
  payroll_register: 'Payroll Register',
  safety_inspection: 'Safety Inspection',
  chemical_inventory: 'Chemical Inventory',
  machine_maintenance: 'Machine Maintenance',
  compliance_certificate: 'Compliance Certificate',
};

export interface Bolt {
  recordId: string;
  ownerMsp: string;
  merkleRoot: string;
  recordType: RecordType;
  period: string;
  site: string;
  /** Rows. In the product's vocabulary, threads. */
  rowCount: number;
  schemaVersion: string;
  committedAt: string;
  block: number;
  status: 'committed' | 'superseded';
  supersededBy: string | null;
}

export const BOLTS: Bolt[] = [
  {
    recordId: 'rc-001', ownerMsp: 'ApexTextileMSP',
    merkleRoot: 'a3f9e2c817b4d056f3a1e79c245b0d3f8c71ae90b6d2f4013e8a95c7d6b02f14',
    recordType: 'payroll_register', period: '2026-07', site: 'Gazipur',
    rowCount: 1847, schemaVersion: 'v2.1.0', committedAt: '2026-08-05T09:14:00Z',
    block: 14821, status: 'committed', supersededBy: null,
  },
  {
    recordId: 'rc-002', ownerMsp: 'ApexTextileMSP',
    merkleRoot: 'c72b19ef4a05d38c6f1b7e2094ad53806cf2913be74a0d5f28e6b1c93470af52',
    recordType: 'safety_inspection', period: '2026-Q2', site: 'Gazipur',
    rowCount: 312, schemaVersion: 'v2.1.0', committedAt: '2026-07-02T10:00:00Z',
    block: 14203, status: 'committed', supersededBy: null,
  },
  {
    recordId: 'rc-003', ownerMsp: 'ApexTextileMSP',
    merkleRoot: '5e81c40db27f9a3e6c05b8114fd7290ae63b5c8021df94a7e3b0682cf159d47a',
    recordType: 'payroll_register', period: '2026-06', site: 'Gazipur',
    rowCount: 1823, schemaVersion: 'v2.0.3', committedAt: '2026-07-04T09:00:00Z',
    block: 13990, status: 'superseded', supersededBy: 'rc-001',
  },
  {
    recordId: 'rc-004', ownerMsp: 'ApexTextileMSP',
    merkleRoot: '9d3a7f26b085e1c4720fa93d5168be47c02195af6e83d740b5c2916ea3f80d6b',
    recordType: 'chemical_inventory', period: '2026-08', site: 'Ashulia',
    rowCount: 64, schemaVersion: 'v2.1.0', committedAt: '2026-08-12T14:20:00Z',
    block: 15044, status: 'committed', supersededBy: null,
  },
  {
    recordId: 'rc-005', ownerMsp: 'ApexTextileMSP',
    merkleRoot: '2f60b9d84e17ca350b9f2e6d8471a0c35d92e7b104fa68c3e05719bd2ac4f803',
    recordType: 'machine_maintenance', period: '2026-07', site: 'Ashulia',
    rowCount: 128, schemaVersion: 'v2.1.0', committedAt: '2026-08-01T11:45:00Z',
    block: 14655, status: 'committed', supersededBy: null,
  },
];

/* -- grants --------------------------------------------------------------- */
export const PURPOSE_CODES: Record<string, string> = {
  'ETH-WAGE-VERIFY': 'Ethical wage verification',
  'CERT-SAFETY-AUDIT': 'Safety certification audit',
  'REACH-COMPLIANCE': 'REACH chemical compliance',
  'ETH-WAGE-BATCH': 'Batch wage audit',
  'MACH-SAFETY-CHECK': 'Machine safety check',
};

export interface Grant {
  grantId: string;
  recordId: string;
  ownerMsp: string;
  requesterMsp: string;
  purposeCode: keyof typeof PURPOSE_CODES | string;
  fieldName: string;
  grantedAt: string;
  expiresAt: string;
  status: 'active' | 'pending' | 'revoked' | 'expired';
  revokedReason: string | null;
}

export const GRANTS: Grant[] = [
  {
    grantId: 'g-001', recordId: 'rc-001', ownerMsp: 'ApexTextileMSP',
    requesterMsp: 'PrimarkSourcingMSP', purposeCode: 'ETH-WAGE-VERIFY',
    fieldName: 'net_pay_bdt', grantedAt: '2026-08-06T09:00:00Z',
    expiresAt: '2026-09-30T00:00:00Z', status: 'active', revokedReason: null,
  },
  {
    grantId: 'g-002', recordId: 'rc-002', ownerMsp: 'ApexTextileMSP',
    requesterMsp: 'BVCertificationMSP', purposeCode: 'CERT-SAFETY-AUDIT',
    fieldName: 'certificate_id', grantedAt: '2026-07-05T09:00:00Z',
    expiresAt: '2026-10-15T00:00:00Z', status: 'active', revokedReason: null,
  },
  {
    grantId: 'g-003', recordId: 'rc-004', ownerMsp: 'ApexTextileMSP',
    requesterMsp: 'NoorGarmentsMSP', purposeCode: 'REACH-COMPLIANCE',
    fieldName: 'svhc_ppm', grantedAt: '2026-08-20T12:00:00Z',
    expiresAt: '2026-09-01T00:00:00Z', status: 'pending', revokedReason: null,
  },
  {
    grantId: 'g-004', recordId: 'rc-003', ownerMsp: 'ApexTextileMSP',
    requesterMsp: 'BVCertificationMSP', purposeCode: 'ETH-WAGE-VERIFY',
    fieldName: 'net_pay_bdt', grantedAt: '2026-06-30T09:00:00Z',
    expiresAt: '2026-07-31T00:00:00Z', status: 'expired', revokedReason: null,
  },
  {
    grantId: 'g-005', recordId: 'rc-001', ownerMsp: 'ApexTextileMSP',
    requesterMsp: 'BVCertificationMSP', purposeCode: 'ETH-WAGE-BATCH',
    fieldName: 'net_pay_bdt', grantedAt: '2026-08-10T09:00:00Z',
    expiresAt: '2026-12-31T00:00:00Z', status: 'revoked',
    revokedReason: 'Requested fields exceeded the agreed audit scope',
  },
];

/* -- verification --------------------------------------------------------- */
export interface ProofStep {
  sibling: string;
  position: 'left' | 'right';
}

export interface Verification {
  receiptId: string;
  verified: boolean;
  recordId: string;
  requesterMsp: string;
  purposeCode: string;
  fieldName: string;
  value: string;
  verifiedAt: string;
  computedRoot: string;
  onChainRoot: string;
  rowsInRecord: number;
  steps: ProofStep[];
  block: number;
  txId: string;
}

/**
 * Deterministic stand-in hashes.
 *
 * A linear expression here produces visible patterns — one seed gave
 * "d5d5d5d5…", which reads instantly as fake. This is an xorshift so the digits
 * look like a digest, while staying reproducible across renders.
 */
const hx = (seed: number): string => {
  let x = (seed * 2654435761) >>> 0 || 1;
  let out = '';
  for (let i = 0; i < 64; i += 1) {
    x ^= x << 13; x >>>= 0;
    x ^= x >>> 17;
    x ^= x << 5; x >>>= 0;
    out += '0123456789abcdef'[x & 15];
  }
  return out;
};

export const VERIFICATION: Verification = {
  receiptId: 'vr-001',
  verified: true,
  recordId: 'rc-001',
  requesterMsp: 'PrimarkSourcingMSP',
  purposeCode: 'ETH-WAGE-VERIFY',
  fieldName: 'net_pay_bdt',
  value: '14,820 BDT',
  verifiedAt: '2026-08-22T17:04:00Z',
  computedRoot: BOLTS[0].merkleRoot,
  onChainRoot: BOLTS[0].merkleRoot,
  rowsInRecord: 1847,
  block: 14821,
  txId: hx(3),
  steps: Array.from({ length: 11 }, (_, i) => ({
    sibling: hx(i + 11),
    position: i % 3 === 0 ? 'left' : 'right',
  })),
};

/* -- the Continuity Gate -------------------------------------------------- */
export interface GateTask {
  taskId: string;
  label: string;
  benchmarkHash: string;
  sealedAt: string;
  previousBp: number;
  candidateBp: number;
  changeBp: number;
  isNewTask: boolean;
  thresholdBp: number;
  pass: boolean;
}

export interface GateDecision {
  candidateId: string;
  parentId: string;
  roundId: string;
  outcome: 'promote' | 'reject';
  reasonCode: string;
  reason: string;
  decidedAt: string;
  candidateHash: string;
  memoryBankHash: string;
  block: number;
  txId: string;
  parameters: { gammaBp: number; tauBp: number; k: number; deltaBp: number };
  endorsers: { mspId: string; fingerprint: string; agreed: boolean; signedBp: number }[];
  perTask: GateTask[];
}

const TASK_LABEL: Record<string, string> = {
  wage_register_inconsistency: 'Wage-register inconsistency',
  forged_certificate: 'Forged compliance certificate',
  chemical_misreporting: 'Chemical-inventory misreporting',
};

const mkTask = (
  taskId: string, prev: number, cand: number, isNew: boolean, seed: number,
): GateTask => ({
  taskId,
  label: TASK_LABEL[taskId],
  benchmarkHash: hx(seed),
  sealedAt: '2026-08-19T00:00:00Z',
  previousBp: prev,
  candidateBp: cand,
  changeBp: cand - prev,
  isNewTask: isNew,
  thresholdBp: isNew ? 200 : -500,
  pass: isNew ? cand - prev >= 200 : prev - cand <= 500,
});

export const GATE_REJECT: GateDecision = {
  candidateId: 'm-v8-rc2', parentId: 'm-v7', roundId: 'round-9',
  outcome: 'reject', reasonCode: 'REGRESSION',
  reason: 'accuracy on wage_register_inconsistency fell by 1805 bp, tolerance is 500 bp',
  decidedAt: '2026-08-21T09:05:00Z',
  candidateHash: hx(21), memoryBankHash: hx(9),
  block: 15102, txId: hx(31),
  parameters: { gammaBp: 200, tauBp: 500, k: 3, deltaBp: 100 },
  endorsers: [
    { mspId: 'ApexTextileMSP', fingerprint: hx(41).slice(0, 40), agreed: true, signedBp: 7350 },
    { mspId: 'NoorGarmentsMSP', fingerprint: hx(43).slice(0, 40), agreed: true, signedBp: 7355 },
    { mspId: 'CrescentFashionMSP', fingerprint: hx(47).slice(0, 40), agreed: true, signedBp: 7345 },
  ],
  perTask: [
    mkTask('wage_register_inconsistency', 9160, 7355, false, 51),
    mkTask('forged_certificate', 9780, 10000, false, 53),
    mkTask('chemical_misreporting', 4800, 10000, true, 59),
  ],
};

export const GATE_PROMOTE: GateDecision = {
  ...GATE_REJECT,
  candidateId: 'm-v8-rc1', roundId: 'round-8',
  outcome: 'promote', reasonCode: 'OK',
  reason: 'gained 5111 bp on chemical_misreporting and lost no more than 500 bp on any earlier task',
  decidedAt: '2026-08-20T12:05:00Z',
  block: 15087,
  perTask: [
    mkTask('wage_register_inconsistency', 9160, 8750, false, 51),
    mkTask('forged_certificate', 9780, 9960, false, 53),
    mkTask('chemical_misreporting', 4800, 9911, true, 59),
  ],
};

export const GATE_STEPS = [
  'Verify benchmark hashes',
  'Collect signed submissions',
  'Check endorsement threshold',
  'Check agreement within δ',
  'Take medians',
  'Test gain on the new task',
  'Test regression on earlier tasks',
];

/* -- model registry ------------------------------------------------------- */
export interface ModelVersion {
  modelId: string;
  parentId: string | null;
  status: 'in_force' | 'promoted' | 'rejected' | 'superseded';
  decidedAt: string;
  reason: string;
  contributors: number;
  memoryBankHash: string;
  accuracies: number[];
}

export const REGISTRY: ModelVersion[] = [
  { modelId: 'm-v8-rc2', parentId: 'm-v7', status: 'rejected', decidedAt: '2026-08-21',
    reason: 'Lost 18.1 points on wage-register inconsistency', contributors: 2,
    memoryBankHash: hx(9), accuracies: [7355, 10000, 10000] },
  { modelId: 'm-v8-rc1', parentId: 'm-v7', status: 'in_force', decidedAt: '2026-08-20',
    reason: 'Gained 51.1 points on the new task, lost nothing beyond tolerance', contributors: 3,
    memoryBankHash: hx(7), accuracies: [8750, 9960, 9911] },
  { modelId: 'm-v7', parentId: 'm-v6', status: 'superseded', decidedAt: '2026-07-28',
    reason: 'Promoted after adding forged-certificate detection', contributors: 3,
    memoryBankHash: hx(5), accuracies: [9160, 9780, 4800] },
  { modelId: 'm-v6', parentId: 'm-v5', status: 'superseded', decidedAt: '2026-06-30',
    reason: 'Promoted on wage-register inconsistency', contributors: 3,
    memoryBankHash: hx(3), accuracies: [9760, 4810, 4690] },
  { modelId: 'm-v5-rc3', parentId: 'm-v5', status: 'rejected', decidedAt: '2026-06-22',
    reason: 'Only 0.4 points gained on the new task; minimum is 2.0', contributors: 2,
    memoryBankHash: hx(2), accuracies: [9740, 4770, 4640] },
];

/* -- governance ----------------------------------------------------------- */
export interface Motion {
  id: string;
  caseNo: string;
  kind: 'new_member' | 'policy_change' | 'suspension';
  title: string;
  body: string;
  status: 'pending' | 'approved';
  required: number;
  endorsers: string[];
  openedAt: string;
  closesAt: string;
  daysLeft: number;
}

export const MOTIONS: Motion[] = [
  {
    id: 'p-001', caseNo: 'BGMEA/2026/M-041', kind: 'new_member',
    title: 'Delta Knitwear Ltd — application for factory membership',
    body: 'Application received from Delta Knitwear Ltd (RJSC-2018-BD-28341) of Narsingdi, operating two facilities with a combined 1,400 machine operators. Preliminary due diligence completed: registration current, no outstanding labour tribunal matters, and both facilities hold valid fire safety certification. Admission requires three of five endorsements under charter §2.1.',
    status: 'pending', required: 3, endorsers: ['ApexTextileMSP', 'NoorGarmentsMSP'],
    openedAt: '2026-08-05', closesAt: '2026-09-26', daysLeft: 26,
  },
  {
    id: 'p-002', caseNo: 'BGMEA/2026/M-038', kind: 'policy_change',
    title: 'Retention of payroll records extended from five years to seven',
    body: 'Proposed amendment to governance charter §4.2, aligning the consortium retention schedule with revised Bangladesh Labour Act regulations taking effect January 2027. Affects commitment metadata retention only; document bodies remain under each member’s own retention policy and deletion rights are unaffected.',
    status: 'approved', required: 4,
    endorsers: ['BGMEAConsortiumMSP', 'ApexTextileMSP', 'NoorGarmentsMSP', 'PrimarkSourcingMSP'],
    openedAt: '2026-05-12', closesAt: '2026-09-02', daysLeft: 2,
  },
  {
    id: 'p-003', caseNo: 'BGMEA/2026/M-044', kind: 'suspension',
    title: 'Crescent Fashion Ltd — suspension review',
    body: 'Repeated failure to serve verification proofs within the agreed four-hour window, on eleven occasions between June and August 2026. Member has been notified and has not responded within the fourteen-day period. Suspension of verification privileges pending review; membership itself is not in question.',
    status: 'pending', required: 4, endorsers: ['BVCertificationMSP'],
    openedAt: '2026-08-22', closesAt: '2026-09-21', daysLeft: 21,
  },
];

/* -- operations ----------------------------------------------------------- */
export const SLA_SERIES = Array.from({ length: 30 }, (_, i) => ({
  day: `08-${String(i + 1).padStart(2, '0')}`,
  uptime: i === 10 ? 97.42 : 99.95 + (i % 4) * 0.015,
  verifications: 28 + ((i * 13) % 61),
  responseMs: i === 10 ? 340 : 150 + ((i * 7) % 45),
}));

export interface Incident {
  id: string;
  severity: 'minor' | 'major';
  summary: string;
  detail: string;
  openedAt: string;
  resolvedAt: string;
  components: string[];
}

export const INCIDENTS: Incident[] = [
  {
    id: 'inc-001', severity: 'minor',
    summary: 'Ordering service leader election during host patching',
    detail: 'orderer0 was restarted for a kernel patch. A new leader was elected in 4.2 seconds. Two verification requests were retried by the client and succeeded. No transactions were lost and no data was affected.',
    openedAt: '2026-08-11T02:14:00Z', resolvedAt: '2026-08-11T02:19:00Z',
    components: ['ordering-service'],
  },
];

/* -- ledger --------------------------------------------------------------- */
export interface Block {
  number: number;
  hash: string;
  previousHash: string;
  timestamp: string;
  channel: string;
  proposer: string;
  txCount: number;
  txs: {
    txId: string;
    chaincode: string;
    fn: string;
    submitter: string;
    endorsers: string[];
    valid: boolean;
    code: string;
  }[];
}

export const BLOCKS: Block[] = Array.from({ length: 24 }, (_, i) => {
  const number = 15102 - i;
  const invalid = i === 6;
  return {
    number,
    hash: hx(number),
    previousHash: hx(number - 1),
    timestamp: `2026-08-${String(31 - Math.floor(i / 2)).padStart(2, '0')}T${String(9 + (i % 12)).padStart(2, '0')}:${String((i * 7) % 60).padStart(2, '0')}:00Z`,
    channel: i % 3 === 0 ? 'model-channel' : 'documents-apex-primark',
    proposer: ['orderer0.bgmea', 'orderer1.bgmea', 'orderer2.apex'][i % 3],
    txCount: 1,
    txs: [
      {
        txId: hx(number * 3),
        chaincode: i % 3 === 0 ? 'fedmodel' : 'doccustody',
        fn: i % 3 === 0 ? 'evaluate_gate' : ['commit_record', 'grant_access', 'record_verification'][i % 3],
        submitter: i % 3 === 0 ? 'BGMEAConsortiumMSP::rafiqul.islam' : 'ApexTextileMSP::fatema.begum',
        endorsers: i % 3 === 0
          ? ['ApexTextileMSP', 'NoorGarmentsMSP', 'CrescentFashionMSP']
          : ['ApexTextileMSP', 'BVCertificationMSP'],
        valid: !invalid,
        code: invalid ? 'MVCC_READ_CONFLICT' : 'VALID',
      },
    ],
  };
});

export const CHAIN_HEIGHT = BLOCKS[0].number;

/* -- auditor bench -------------------------------------------------------- */
export interface QueueItem {
  id: string;
  factory: string;
  recordType: string;
  period: string;
  commitmentId: string;
  state: 'queued' | 'checking' | 'passed' | 'failed';
}

export const QUEUE: QueueItem[] = [
  { id: 'q1', factory: 'Apex Textile Ltd', recordType: 'Payroll Register', period: '2026-07', commitmentId: 'rc-001', state: 'passed' },
  { id: 'q2', factory: 'Apex Textile Ltd', recordType: 'Safety Inspection', period: '2026-Q2', commitmentId: 'rc-002', state: 'passed' },
  { id: 'q3', factory: 'Noor Garments Ltd', recordType: 'Chemical Inventory', period: '2026-08', commitmentId: 'rc-104', state: 'queued' },
  { id: 'q4', factory: 'Noor Garments Ltd', recordType: 'Machine Maintenance', period: '2026-07', commitmentId: 'rc-105', state: 'queued' },
  { id: 'q5', factory: 'Crescent Fashion Ltd', recordType: 'Payroll Register', period: '2026-07', commitmentId: 'rc-201', state: 'queued' },
  { id: 'q6', factory: 'Crescent Fashion Ltd', recordType: 'Safety Inspection', period: '2026-Q2', commitmentId: 'rc-202', state: 'queued' },
];

/* -- shift log ------------------------------------------------------------ */
export interface LogEntry {
  at: string;
  kind: 'seal' | 'grant' | 'revoke' | 'verify' | 'request';
  text: string;
}

export const SHIFT_LOG: LogEntry[] = [
  { at: '31 Aug · 14:02', kind: 'verify', text: 'Primark Sourcing verified net_pay_bdt on rc-001' },
  { at: '22 Aug · 16:45', kind: 'revoke', text: 'Access revoked — BV Certification exceeded agreed scope' },
  { at: '20 Aug · 12:00', kind: 'request', text: 'Noor Garments requested chemical inventory access' },
  { at: '12 Aug · 14:20', kind: 'seal', text: 'Chemical inventory 2026-08 sealed in block #15,044' },
  { at: '06 Aug · 09:00', kind: 'grant', text: 'Access granted to Primark Sourcing — one field, 55 days' },
  { at: '05 Aug · 09:14', kind: 'seal', text: 'Payroll register 2026-07 sealed in block #14,821' },
  { at: '01 Aug · 11:45', kind: 'seal', text: 'Machine maintenance 2026-07 sealed in block #14,655' },
];

/* -- the limitations, verbatim from the report ---------------------------- */
export const LIMITATIONS = [
  'Every result is a simulation on invented data. Not a measurement of any factory.',
  'Our own benchmark cannot validate the learning claim — a model trained on summaries alone matched the full system.',
  'We removed one of our own mechanisms after measuring that it cost 3.9 points of accuracy.',
  'We chose the difficulty setting, and it sits near the value that makes the baseline look worst.',
  'Our added noise is not differential privacy. No sensitivity bound, no budget, and released variances carry no noise at all.',
  'The simulation omits every privacy and robustness component the design specifies, so the reported accuracy is an upper bound.',
  'Secure aggregation, robust averaging and contribution scoring cannot all three hold. We gave up the first.',
  'A signed record of a false statement is still a correct record of a lie. The first-mile problem is mitigated, not solved.',
  'Infrastructure is costed from published list prices, and the audit saving depends on buyers accepting cryptographic evidence.',
];

/* -- comparison matrix ---------------------------------------------------- */
export const MATRIX = {
  columns: ['Ledger', 'Internal records', 'Shared model', 'Learns over time', 'Gate on past tasks'],
  rows: [
    { name: 'TextileGenesis / TrusTrace', cells: [true, false, false, false, false] },
    { name: 'AWARE & DigiProd Pass (BGMEA)', cells: [true, false, false, false, false] },
    { name: 'Guardtime & OpenTimestamps', cells: [true, true, false, false, false] },
    { name: 'Swarm Learning', cells: [true, false, true, false, false] },
    { name: 'LiFeChain', cells: [true, false, true, true, false] },
    { name: 'Breadcrumbs', cells: [true, true, true, true, true] },
  ],
};
