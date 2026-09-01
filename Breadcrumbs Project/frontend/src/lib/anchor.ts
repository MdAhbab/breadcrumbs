/**
 * The four ledger mechanisms, as the API returns them.
 *
 * These are fixtures, not a client. The rest of this application is built the
 * same way — every screen renders from `data.ts` rather than from a running
 * backend — so introducing a live fetch for six components alone would make the
 * demo depend on a server being up and would leave the app half one thing and
 * half another.
 *
 * The shapes below are copied from the API responses field for field
 * (`/api/seals`, `/api/completeness`, `/api/records/{id}/witness-requirement`,
 * `/api/anchor/epochs`, `/api/records/{id}/verify`, `/api/anchor/non-membership`),
 * so wiring them to `fetch` later is a change of source, not of type.
 *
 * Every group element is a hex string. A 3072-bit integer does not survive
 * `JSON.parse` as a number, and the backend refuses to emit one.
 */

/* ---------------------------------------------------------------- seals --- */
export interface Amendment {
  version: number;
  previous_count: number;
  previous_root: string;
  added: string[];
  reason: string;
  amended_at: string;
  amended_by: string;
}

export interface PeriodSeal {
  bucket: string;
  site: string;
  record_type: string;
  period: string;
  owner_msp: string;
  record_count: number;
  records_root: string;
  sealed_at: string;
  sealed_by: string;
  status: 'sealed';
  version: number;
  amendments: Amendment[];
}

export interface Completeness {
  bucket: string;
  sealed: boolean;
  complete: boolean;
  sealed_count?: number;
  disclosed_count?: number;
  sealed_root?: string;
  computed_root?: string;
  amendment_count?: number;
  reason: string;
}

/* ------------------------------------------------------------ witnesses --- */
/** In increasing evidentiary weight. A screen that treats these as equal lies. */
export const CHECK_CODES = {
  format_only: {
    label: 'Format only',
    weight: 1,
    note: 'The witness confirmed the file parses and the columns match the schema. It did not look at a value.',
  },
  sample_row_recompute: {
    label: 'Sample row recompute',
    weight: 2,
    note: 'The witness recomputed a sample of rows against the declared totals.',
  },
  source_system_readback: {
    label: 'Source system readback',
    weight: 3,
    note: 'The witness read the same figures back out of the factory’s own payroll system.',
  },
  physical_presence: {
    label: 'Physical presence',
    weight: 4,
    note: 'The witness was on site while the record was produced.',
  },
} as const;

export type CheckCode = keyof typeof CHECK_CODES;

export interface Attestation {
  witness_msp: string;
  check_code: CheckCode;
  attested_at: string;
}

export interface WitnessRequirement {
  in_force: boolean;
  required: boolean;
  round_id?: string;
  witnesses: string[];
  pool_size?: number;
  reason?: string;
  attestations: Attestation[];
  attested_by: string[];
}

/* ---------------------------------------------------------- accumulator --- */
export interface Beacon {
  input_hex: string;
  output_hex: string;
  iterations: number;
  published_at: string;
  published_by: string;
}

export interface Epoch {
  epoch: number;
  digest: string;
  value_hex: string;
  size: number;
  element_count: number;
  sealed_at: string;
  beacon?: Beacon;
}

export interface AnchorState {
  installed: boolean;
  value_hex?: string;
  epoch?: number;
  size?: number;
  modulus_bits?: number;
  dealer?: string;
  reason?: string;
}

/* --------------------------------------------------------- verification --- */
export interface Check {
  id: 'ledger' | 'witness' | 'index';
  label: string;
  ok: boolean;
  detail: string;
  forgeable_by_trapdoor: boolean;
}

export interface Verification {
  record_id: string;
  anchored: boolean;
  epoch?: number;
  checks: Check[];
  verified: boolean;
  reason: string;
  note: string;
}

export interface Absence {
  reference: string;
  provable: boolean;
  epoch?: number;
  ledger_holds_record: boolean;
  never_committed: boolean;
  proof_ok: boolean;
  reason: string;
  scope: string;
}

/* ========================================================== the fixtures === */
const NARAYANGANJ = 'ApexTextileMSP|Narayanganj|payroll_register|2026-05';

export const SEALS: PeriodSeal[] = [
  {
    bucket: NARAYANGANJ,
    site: 'Narayanganj',
    record_type: 'payroll_register',
    period: '2026-05',
    owner_msp: 'ApexTextileMSP',
    record_count: 5,
    records_root: '9f2c41ab77de05b3e1c8a4f60d92bb37c5e08a1d4f6b92c30e7a58d1bc463f20',
    sealed_at: '2026-07-01T10:00:00Z',
    sealed_by: 'fatema.begum',
    status: 'sealed',
    version: 2,
    amendments: [
      {
        version: 1,
        previous_count: 5,
        previous_root: '1a4e77c0b2d95f38e6ac10bb47f2093d5e8c6a1f0b34d729e5c81af60d3b92e4',
        added: ['rc-071'],
        reason: 'register re-declared after the Narayanganj line reconciliation',
        amended_at: '2026-07-03T11:00:00Z',
        amended_by: 'fatema.begum',
      },
    ],
  },
  {
    bucket: 'ApexTextileMSP|Gazipur|safety_inspection|2026-Q2',
    site: 'Gazipur',
    record_type: 'safety_inspection',
    period: '2026-Q2',
    owner_msp: 'ApexTextileMSP',
    record_count: 3,
    records_root: '4b81d0e6f39a27c5108bd4e2fa60937c8e5d1b0a2f74c396e8ad50b17f2c6e9d',
    sealed_at: '2026-07-08T14:30:00Z',
    sealed_by: 'fatema.begum',
    status: 'sealed',
    version: 1,
    amendments: [],
  },
];

/** What the factory sealed, and what the buyer was actually handed. */
export const SEALED_IDS = ['rc-071', 'rc-072', 'rc-073', 'rc-074', 'rc-075'];
export const DISCLOSED_IDS = ['rc-071', 'rc-072', 'rc-073', 'rc-074'];

export const WITNESS: Record<string, WitnessRequirement> = {
  // Assigned, witnessed, and the strongest check code claimed.
  'rc-001': {
    in_force: true,
    required: true,
    round_id: 'sr-001',
    witnesses: ['BVCertificationMSP', 'NoorGarmentsMSP'],
    pool_size: 4,
    attestations: [
      { witness_msp: 'BVCertificationMSP', check_code: 'source_system_readback', attested_at: '2026-08-05T09:12:00Z' },
      { witness_msp: 'NoorGarmentsMSP', check_code: 'format_only', attested_at: '2026-08-05T09:13:00Z' },
    ],
    attested_by: ['BVCertificationMSP', 'NoorGarmentsMSP'],
  },
  // Required, and one of the two assigned witnesses never signed.
  'rc-004': {
    in_force: true,
    required: true,
    round_id: 'sr-001',
    witnesses: ['BVCertificationMSP', 'CrescentFashionMSP'],
    pool_size: 4,
    attestations: [
      { witness_msp: 'BVCertificationMSP', check_code: 'format_only', attested_at: '2026-08-12T14:19:00Z' },
    ],
    attested_by: ['BVCertificationMSP'],
  },
  // Not selected by the sample. Nothing is wrong; the screen must not imply it.
  'rc-005': {
    in_force: true,
    required: false,
    round_id: 'sr-001',
    witnesses: [],
    pool_size: 4,
    attestations: [],
    attested_by: [],
  },
  // The rule is off on this channel. The screen says so rather than showing a
  // reassuring empty state.
  'rc-002': {
    in_force: false,
    required: false,
    witnesses: [],
    reason: 'the consortium has not adopted the witness rule on this channel',
    attestations: [],
    attested_by: [],
  },
};

export const ANCHOR_STATE: AnchorState = {
  installed: true,
  value_hex:
    'a3f1c08bd47e29a6f350bc12e8d47a09'
    + 'b6e35c81f0a294d7e6c308bb5f19a24d'
    + '7f0e52ac9b184d3e60ca7f21b8d05e93',
  epoch: 4,
  size: 27,
  modulus_bits: 3072,
  dealer: 'BGMEAConsortiumMSP',
};

export const EPOCHS: Epoch[] = [
  {
    epoch: 1, digest: 'c81f0a294d7e6c308bb5f19a24d7f0e52ac9b184d3e60ca7f21b8d05e93a3f1c0',
    value_hex: '5e93a3f1c08bd47e29a6f350bc12e8d4', size: 6, element_count: 6,
    sealed_at: '2026-07-06T09:30:00Z',
    beacon: { input_hex: '2ac9b184', output_hex: 'd3e60ca7', iterations: 1_048_576, published_at: '2026-07-06T10:04:00Z', published_by: 'BGMEAConsortiumMSP' },
  },
  {
    epoch: 2, digest: '7f0e52ac9b184d3e60ca7f21b8d05e93a3f1c08bd47e29a6f350bc12e8d47a09',
    value_hex: 'bc12e8d47a09b6e35c81f0a294d7e6c3', size: 14, element_count: 8,
    sealed_at: '2026-07-20T09:30:00Z',
    beacon: { input_hex: '9b184d3e', output_hex: '60ca7f21', iterations: 1_048_576, published_at: '2026-07-20T10:06:00Z', published_by: 'BGMEAConsortiumMSP' },
  },
  {
    // The failing path: a beacon claiming less work than the consortium agreed.
    epoch: 3, digest: '0a294d7e6c308bb5f19a24d7f0e52ac9b184d3e60ca7f21b8d05e93a3f1c08bd',
    value_hex: '5c81f0a294d7e6c308bb5f19a24d7f0e', size: 21, element_count: 7,
    sealed_at: '2026-08-03T09:30:00Z',
    beacon: { input_hex: '4d3e60ca', output_hex: '7f21b8d0', iterations: 65_536, published_at: '2026-08-03T09:41:00Z', published_by: 'BGMEAConsortiumMSP' },
  },
  {
    // No beacon at all. Order is proved; elapsed time is not.
    epoch: 4, digest: 'b8d05e93a3f1c08bd47e29a6f350bc12e8d47a09b6e35c81f0a294d7e6c308bb5',
    value_hex: 'a3f1c08bd47e29a6f350bc12e8d47a09', size: 27, element_count: 6,
    sealed_at: '2026-08-17T09:30:00Z',
  },
];

/** What the consortium agreed a beacon must cost, per epoch. */
export const MINIMUM_ITERATIONS = 1_048_576;

export const VERIFICATIONS: Record<string, Verification> = {
  'rc-001': {
    record_id: 'rc-001',
    anchored: true,
    epoch: 4,
    verified: true,
    reason: '',
    checks: [
      { id: 'ledger', label: 'The ledger holds this record, with this root', ok: true, detail: 'committed in ApexTextileMSP|Gazipur|payroll_register|2026-07 by ApexTextileMSP', forgeable_by_trapdoor: false },
      { id: 'witness', label: 'The accumulator witness verifies', ok: true, detail: 'verified against epoch 4', forgeable_by_trapdoor: true },
      { id: 'index', label: 'The element is in the anchored index', ok: true, detail: 'admitted by epoch 2', forgeable_by_trapdoor: false },
    ],
    note: 'The modulus came from a trusted-dealer ceremony, so whoever holds its factorisation could forge check 2. Checks 1 and 3 are what make that forgery fail anyway, which is why all three are shown.',
  },
  // The trapdoor forgery. Check 2 passes; 1 and 3 are what catch it.
  'rc-forged': {
    record_id: 'rc-forged',
    anchored: true,
    epoch: 4,
    verified: false,
    reason: 'no epoch ever admitted this element',
    checks: [
      { id: 'ledger', label: 'The ledger holds this record, with this root', ok: false, detail: 'the ledger holds no record rc-forged', forgeable_by_trapdoor: false },
      { id: 'witness', label: 'The accumulator witness verifies', ok: true, detail: 'verified against epoch 4', forgeable_by_trapdoor: true },
      { id: 'index', label: 'The element is in the anchored index', ok: false, detail: 'no epoch ever admitted this element; the witness was not issued by one', forgeable_by_trapdoor: false },
    ],
    note: 'The modulus came from a trusted-dealer ceremony, so whoever holds its factorisation could forge check 2. Checks 1 and 3 are what make that forgery fail anyway, which is why all three are shown.',
  },
  // A witness issued three epochs ago. Stale, not forged — and the difference
  // matters to whoever has to decide what to do next.
  'rc-003': {
    record_id: 'rc-003',
    anchored: true,
    epoch: 4,
    verified: false,
    reason: 'witness is for epoch 1, accumulator is at epoch 4',
    checks: [
      { id: 'ledger', label: 'The ledger holds this record, with this root', ok: true, detail: 'committed in ApexTextileMSP|Gazipur|payroll_register|2026-06 by ApexTextileMSP', forgeable_by_trapdoor: false },
      { id: 'witness', label: 'The accumulator witness verifies', ok: false, detail: 'witness is for epoch 1, accumulator is at epoch 4', forgeable_by_trapdoor: true },
      { id: 'index', label: 'The element is in the anchored index', ok: true, detail: 'admitted by epoch 1', forgeable_by_trapdoor: false },
    ],
    note: 'The modulus came from a trusted-dealer ceremony, so whoever holds its factorisation could forge check 2. Checks 1 and 3 are what make that forgery fail anyway, which is why all three are shown.',
  },
};

export const ABSENCE: Record<string, Absence> = {
  'ISO45001-FORGED-Q3-2026': {
    reference: 'ISO45001-FORGED-Q3-2026',
    provable: true,
    epoch: 4,
    ledger_holds_record: false,
    never_committed: true,
    proof_ok: true,
    reason: '',
    scope: 'This proves the canonical element for ‘ISO45001-FORGED-Q3-2026’ was never accumulated up to epoch 4. It says nothing about later epochs, and nothing about documents that were never offered to this ledger at all.',
  },
  'rc-001': {
    reference: 'rc-001',
    provable: true,
    epoch: 4,
    ledger_holds_record: true,
    never_committed: false,
    proof_ok: false,
    reason: 'Bezout relation does not hold; the element may in fact be a member',
    scope: 'This proves the canonical element for ‘rc-001’ was never accumulated up to epoch 4. It says nothing about later epochs, and nothing about documents that were never offered to this ledger at all.',
  },
};
