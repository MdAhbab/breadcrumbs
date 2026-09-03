/*
 * The API client, and the only place the frontend knows a network exists.
 *
 * Every interface below is the shape the backend actually returns, checked
 * against live responses rather than transcribed from a design. Where a field
 * can be null the type says so — `uptime_pct: number | null` is not defensive
 * programming, it is the API reporting that this prototype does not measure
 * uptime, and a screen that types it as `number` will quietly render a zero
 * instead of saying "not measured".
 *
 * There are no fixtures here. The previous version of this app shipped its
 * whole world as literals in `data.ts`, which meant every screen was a drawing
 * of a system rather than a view of one.
 */

const BASE: string = (import.meta.env.VITE_API_URL as string | undefined)
  ?? 'http://localhost:8000';

const TOKEN_KEY = 'breadcrumbs.token';
const ROLE_KEY = 'breadcrumbs.role';

/* -- credentials ---------------------------------------------------------- */
/*
 * Held here rather than in the React tree so a plain `api()` call from an event
 * handler carries the session without threading a token through every prop.
 */
function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    // Private window, or site data blocked. Not an error — just no session.
    return null;
  }
}

let token: string | null = readStored(TOKEN_KEY);

export function setCredentials(nextToken: string, roleId: string): void {
  token = nextToken;
  try {
    localStorage.setItem(TOKEN_KEY, nextToken);
    localStorage.setItem(ROLE_KEY, roleId);
  } catch {
    /* the session lives for this page only */
  }
}

export function clearCredentials(): void {
  token = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
  } catch {
    /* nothing to do */
  }
}

export const storedRole = (): string | null => readStored(ROLE_KEY);
export const hasToken = (): boolean => token !== null;

/* -- transport ------------------------------------------------------------ */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /** True when the caller is signed in but not entitled — a scoping refusal. */
  get denied(): boolean {
    return this.status === 403;
  }

  get missing(): boolean {
    return this.status === 404;
  }
}

/**
 * Pull the contract's own sentence out of whatever envelope it arrived in.
 *
 * FastAPI wraps `HTTPException` detail, the chaincode handler returns a bare
 * `{code, message}`, and a validation error returns a list. The interface shows
 * the reason — "grant covers net_pay_bdt, not national_id" tells a user what to
 * do and "400 Bad Request" does not — so it is worth unwrapping all three.
 */
function readError(status: number, body: unknown): ApiError {
  const seen = body as Record<string, unknown> | null;
  const detail = seen?.detail ?? seen;

  if (typeof detail === 'string') return new ApiError(status, detail);
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    return new ApiError(status, first?.msg ?? 'the request was not accepted');
  }
  if (detail && typeof detail === 'object') {
    const d = detail as { message?: string; code?: string };
    if (d.message) return new ApiError(status, d.message, d.code);
  }
  return new ApiError(status, `request failed (${status})`);
}

let onUnauthorized: (() => void) | null = null;

/** Called when a token is rejected, so the session layer can sign out once. */
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    // A network failure is a different problem from a refusal, and the screens
    // say so: one means the API is not running, the other means you may not.
    throw new ApiError(
      0,
      `Cannot reach the Breadcrumbs API at ${BASE}. Start it with: `
      + 'uvicorn app.main:app --port 8000',
      'NO_BACKEND',
    );
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const body: unknown = text ? JSON.parse(text) : null;

  if (!response.ok) {
    if (response.status === 401) {
      clearCredentials();
      onUnauthorized?.();
    }
    throw readError(response.status, body);
  }
  return body as T;
}

export const get = <T>(path: string): Promise<T> => request<T>(path);

export const post = <T>(path: string, body?: unknown): Promise<T> =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body ?? {}) });

/* -- domain types --------------------------------------------------------- */
export type RoleId = 'factory' | 'buyer' | 'auditor' | 'consortium' | 'regulator';

export interface RoleOption {
  role: RoleId;
  label: string;
  org: string;
  person: string;
  summary: string;
  landing: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: RoleId;
  org: string;
  person: string;
  landing: string;
}

export interface Principal {
  role: RoleId;
  msp_id: string;
  org: string;
  person: string;
  label: string;
  read_only: boolean;
}

export interface Attestation {
  witness_msp: string;
  check_code: CheckCode;
  attested_at: string;
  signature: string;
}

export interface LedgerRecord {
  record_id: string;
  owner_msp: string;
  merkle_root: string;
  record_type: string;
  period: string;
  site: string;
  row_count: number;
  bucket: string;
  schema_version: string;
  committed_at: string;
  committed_by: string;
  status: 'committed' | 'superseded';
  superseded_by: string | null;
  witnesses: string[];
  attestations: Attestation[];
}

export interface Receipt {
  receipt_id: string;
  grant_id: string;
  record_id: string;
  verifier_msp: string;
  field_name: string;
  result: 'match' | 'no_match';
  computed_root: string;
  verified_at: string;
}

export interface RecordDetail {
  record: LedgerRecord;
  receipts: Receipt[];
  rows_held_off_chain: number;
}

export interface Grant {
  grant_id: string;
  record_id: string;
  owner_msp: string;
  requester_msp: string;
  purpose_code: string;
  field_name: string;
  granted_at: string;
  expires_at: string;
  status: 'active' | 'revoked' | 'expired' | 'pending';
  revoked_reason: string | null;
}

export interface Amendment {
  version: number;
  added: string[];
  reason: string;
  amended_at: string;
  amended_by: string;
  previous_count: number;
  previous_root: string;
}

export interface Reopening {
  at_version: number;
  reason: string;
  reopened_at: string;
  reopened_by: string;
  count_when_reopened: number;
  root_when_reopened: string;
}

export interface PeriodSeal {
  bucket: string;
  owner_msp: string;
  site: string;
  record_type: string;
  period: string;
  record_count: number;
  records_root: string;
  sealed_at: string;
  sealed_by: string;
  status: 'sealed' | 'reopened';
  version: number;
  amendments: Amendment[];
  reopenings?: Reopening[];
}

export interface Completeness {
  bucket: string;
  sealed: boolean;
  complete: boolean;
  status?: 'sealed' | 'reopened';
  sealed_count?: number;
  disclosed_count?: number;
  sealed_root?: string;
  computed_root?: string;
  amendment_count?: number;
  reason: string;
}

/**
 * What a witness can claim to have done, in increasing evidentiary weight.
 *
 * The ladder is the point. "Format only" and "physical presence" are both
 * attestations and they are not remotely the same evidence, so the weight is
 * carried here and drawn on screen rather than left for a reader to infer from
 * a snake_case string.
 */
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
    note: 'The witness read the same figures back out of the factory\u2019s own payroll system.',
  },
  physical_presence: {
    label: 'Physical presence',
    weight: 4,
    note: 'The witness was on site while the record was produced.',
  },
} as const;

export type CheckCode = keyof typeof CHECK_CODES;

export interface WitnessRequirement {
  in_force: boolean;
  required: boolean;
  round_id?: string;
  witnesses: string[];
  pool_size?: number;
  reason?: string;
  attestations: Attestation[];
  attested_by: string[];
  committed_at?: string;
  round_opened_at?: string;
  /** Committed before the consortium adopted the rule: nothing was required. */
  predates_rule?: boolean;
}

export interface AnchorState {
  installed: boolean;
  epoch?: number;
  size?: number;
  value_hex?: string;
  parameters_hash?: string;
  updated_at?: string;
  /** The delay work the consortium expects each epoch to carry. */
  minimum_iterations?: number;
  reason?: string;
}

export interface Beacon {
  input_hex: string;
  output_hex: string;
  iterations: number;
  published_at: string;
  published_by: string;
  proof: { kind: string; iterations: number; challenge_hex: string; proof_hex: string };
}

export interface Epoch {
  epoch: number;
  digest: string;
  accumulator_hex: string;
  previous_hex: string;
  element_count: number;
  size: number;
  parameters_hash: string;
  sealed_at: string;
  beacon?: Beacon;
}

export interface SeedRound {
  round_id: string;
  members: string[];
  sample_percent: number;
  quorum: number;
  status: string;
  opened_at: string;
  opened_by?: string;
  commitments?: Record<string, string>;
  shares?: Record<string, string | null>;
  seed?: string | null;
}

export interface Notification {
  id: string;
  audience_msp: string;
  kind: string;
  body: string;
  created_at: string;
  read: boolean;
}

export interface AnchorGroup {
  installed: boolean;
  params?: {
    modulus_hex: string;
    modulus_bits: number;
    generator_hex: string;
    suite: string;
    provenance: string;
  };
  transcript?: {
    dealer: string;
    contributors: string[];
    contribution_hashes: Record<string, string>;
    modulus_bits: number;
    parameters_hash: string;
    note: string;
  };
  reason?: string;
}

export interface VerificationCheck {
  id: 'ledger' | 'witness' | 'index';
  label: string;
  ok: boolean;
  detail: string;
  /** Only the accumulator witness can be forged by a trapdoor holder. */
  forgeable_by_trapdoor: boolean;
}

export interface Verification {
  record_id: string;
  anchored: boolean;
  epoch: number | null;
  checks: VerificationCheck[];
  verified: boolean;
  reason: string;
  witness: Record<string, unknown> | null;
  note: string;
}

export interface Absence {
  reference: string;
  provable: boolean;
  epoch: number | null;
  ledger_holds_record: boolean;
  never_committed: boolean;
  proof_ok: boolean;
  reason: string;
  witness: Record<string, unknown> | null;
  scope: string;
}

export interface PublicReceipt {
  receipt: Receipt;
  record: {
    record_id: string; record_type: string; period: string; site: string;
    owner_msp: string; row_count: number; committed_at: string; status: string;
  } | null;
  on_chain_root: string | null;
  root_matches: boolean;
  note: string;
}

export interface RowProof {
  verified: boolean;
  verdict: string;
  disclosed: { field_name: string; value: string | number };
  proof: {
    computed_root: string;
    on_chain_root: string;
    match: boolean;
    steps: { sibling: string; position: 'left' | 'right' }[];
    ladder: string[];
    rows_in_record: number;
    rows_disclosed: number;
  };
  receipt: Receipt;
  tx_id: string;
  block: number;
}

export interface GateTask {
  task_id: string;
  benchmark_hash: string;
  previous_bp: number;
  candidate_bp: number;
  change_bp: number;
  is_new_task: boolean;
  threshold_bp: number;
  pass: boolean;
  /**
   * The best this task has ever scored under a promoted model, and how far the
   * candidate sits below it.
   *
   * Both are null when nothing has been promoted on the task yet: there is no
   * history to have drifted from. That is a different statement from zero and
   * the interface has to render it differently, or a first-ever candidate looks
   * like one that exactly matched a record it was never measured against.
   *
   * `drift_from_best_bp` is negative when the candidate is *above* the record.
   */
  best_bp: number | null;
  drift_from_best_bp: number | null;
}

export interface DetectorStatus {
  trained: boolean;
  reason?: string;
  arm?: string;
  features?: number;
  parameters?: number;
  weights_bytes?: number;
  threshold?: number;
  false_positive_budget?: number;
  chosen_on?: string;
  measured?: {
    detection: number | null;
    false_positive: number | null;
    balanced_accuracy: number | null;
    roc_auc: number | null;
    seeds: number;
  };
  detection_by_kind?: Record<string, number | null>;
  blind_to?: { kind: string; detection: number | null; why: string };
  note?: string;
}

export interface Screening extends DetectorStatus {
  record_id: string;
  scored: boolean;
  score?: number;
  threshold?: number;
  flagged?: boolean;
  likely_kind?: string | null;
  per_class?: Record<string, number>;
  features_used?: number;
  verdict?: string;
  caveat?: string;
}

export interface HighWater {
  marks: Record<string, number | null>;
  note: string;
}

export interface ModelVersion {
  model_id: string;
  model_hash: string;
  parent_id: string;
  round_id: string;
  memory_bank_hash: string;
  contributors: string[];
  endorsers: string[];
  status: 'promoted' | 'rejected' | 'superseded';
  outcome_reason: string;
  per_task: GateTask[];
  decided_at: string;
}

export interface GateDecision {
  round_id: string;
  candidate_id: string;
  candidate_hash: string;
  parent_id: string;
  memory_bank_hash: string;
  contributors: string[];
  endorsers: string[];
  rejected_submissions: { endorser_msp: string; reason: string }[];
  parameters: {
    gamma_bp: number;
    tau_bp: number;
    k: number;
    delta_bp: number;
    /** The cumulative bound, against a task's best-ever score. */
    sigma_bp?: number;
  };
  decided_at: string;
  per_task: GateTask[];
  outcome: 'promote' | 'reject';
  /** 'OK' | 'REGRESSION' | 'CUMULATIVE_REGRESSION' | 'NO_GAIN' | … */
  reason_code: string;
  reason: string;
}

export interface TrainingRound {
  round_id: string;
  tasks: string[];
  contributors: string[];
  memory_bank_hash: string;
  opened_at: string;
  opened_by: string;
  status: string;
  decision?: 'promote' | 'reject';
}

export interface Benchmark {
  task_id: string;
  benchmark_hash: string;
  contributors: string[];
  size: number;
  committed_at: string;
  committed_by: string;
  revealed: boolean;
  revealed_at: string | null;
}

export interface MemoryBank {
  anchored_hashes: { round_id: string; memory_bank_hash: string }[];
  privacy_note: string;
  contains: string;
}

export interface Proposal {
  id: string;
  kind: 'new_member' | 'policy_change' | 'suspension';
  title: string;
  body: string;
  status: 'pending' | 'approved';
  required: number;
  endorsers: string[];
  opened_at: string;
  closes_at: string;
  endorsement_count: number;
  threshold_reached: boolean;
}

export interface Org {
  msp_id: string;
  name: string;
  kind: 'factory' | 'buyer' | 'auditor' | 'consortium' | 'regulator';
  kind_label: string;
  country: string;
  channels: string[];
  is_you: boolean;
}

export interface ActivityEvent {
  at: string;
  kind: 'seal' | 'grant' | 'revoke' | 'verify' | 'request';
  text: string;
  function: string;
  chaincode: string;
  channel: string;
  block: number;
  tx_id: string;
  valid: boolean;
}

export interface QueueItem {
  grant_id: string;
  record_id: string;
  owner_msp: string;
  record_type: string;
  period: string;
  site: string;
  row_count: number;
  field_name: string;
  purpose_code: string;
  grant_status: string;
  state: 'queued' | 'passed' | 'failed' | 'revoked';
  receipt_id: string | null;
  verified_at: string | null;
}

export interface AuditQueue {
  items: QueueItem[];
  attestations: {
    id: string;
    claim_code: string;
    evidence_scope: string;
    statement: string;
    status: string;
    signed_at: string;
    auditor_name: string;
  }[];
}

export interface AccessRequest {
  id: string;
  requester_msp: string;
  supplier_msp: string;
  record_type: string;
  period: string;
  item_reference: string | null;
  purpose_code: string;
  field_name: string;
  expires_at: string;
  status: 'pending' | 'granted' | 'declined';
  grant_id: string | null;
  requested_at: string;
}

export interface Incident {
  id: string;
  severity: 'minor' | 'major';
  summary: string;
  detail: string;
  opened_at: string;
  resolved_at: string | null;
  components: string[];
}

export interface Sla {
  points: {
    day: string;
    verifications: number;
    uptime_pct: number | null;
    avg_response_ms: number | null;
  }[];
  kpis: {
    total_verifications: number;
    days_observed: number;
    monthly_uptime_pct: number | null;
    uptime_target_pct: number;
    avg_response_ms: number | null;
    response_target_ms: number;
    rpo: string;
    rto: string;
  };
  unmeasured: { fields: string[]; reason: string };
  incidents: Incident[];
}

export interface Channel {
  channel: string;
  height: number;
  head_hash: string;
  integrity_ok: boolean;
  integrity_detail: string;
  members: string[];
}

export interface Block {
  number: number;
  block_hash: string;
  previous_hash: string;
  data_hash: string;
  timestamp: string;
  proposer: string;
  transaction_count: number;
  transactions: {
    tx_id: string;
    chaincode: string;
    function: string;
    submitter: string;
    endorsers: string[];
    validation: string;
    valid: boolean;
    reads: string[];
    writes: string[];
  }[];
}

export interface Provenance {
  corpus: 'present' | 'absent';
  note: string;
  seed?: number;
  scale?: string;
  anomaly_rate?: number;
  dirichlet_alpha?: number;
  periods?: string;
  total_documents?: number;
  sites?: string[];
  adversary_events?: number;
  manifest_sha256?: string;
  records_on_ledger?: number;
  excluded_by_schema?: number;
  excluded_reason?: string;
  seals?: number;
}

export interface About {
  provenance: Provenance;
  gate: { promoted: GateDecision | null; rejected: GateDecision | null };
  windows: { site: string; period: string; reason: string }[];
  limitations: string[];
  comparison: { columns: string[]; rows: { name: string; cells: boolean[] }[] };
}

export interface Health {
  status: string;
  channels: Channel[];
  ledger_integrity: boolean;
  provenance: Provenance;
  note: string;
}

export interface RegulatorOverview {
  read_only_notice: string;
  kpis: {
    active_factories: number;
    total_organisations: number;
    open_proposals: number;
    schema_versions_in_use: number;
  };
  governance_events: {
    kind: string; title: string; status: string; opened_at: string; org: string;
  }[];
  chain: Channel[];
}

/* -- endpoints ------------------------------------------------------------ */
export const api = {
  roles: () => get<RoleOption[]>('/api/auth/roles'),
  signIn: (role: string, code: string) =>
    post<TokenResponse>('/api/auth/verify', { role, code }),
  me: () => get<Principal>('/api/auth/me'),

  health: () => get<Health>('/api/health'),
  about: () => get<About>('/api/about'),
  orgs: () => get<Org[]>('/api/orgs'),
  activity: (limit = 40) => get<ActivityEvent[]>(`/api/activity?limit=${limit}`),

  records: () => get<LedgerRecord[]>('/api/records'),
  record: (id: string) => get<RecordDetail>(`/api/records/${encodeURIComponent(id)}`),
  commitRecord: (body: {
    record_id: string; record_type: string; period: string; site: string;
    schema_version: string; rows: Record<string, unknown>[];
  }) => post<{ record_id: string; merkle_root: string; row_count: number; tx_id: string; block: number }>(
    '/api/records', body,
  ),

  grants: () => get<Grant[]>('/api/grants'),
  grant: (body: {
    grant_id: string; record_id: string; requester_msp: string;
    purpose_code: string; field_name: string; expires_at: string;
  }) => post('/api/grants', body),
  revoke: (grantId: string, reason: string) =>
    post(`/api/grants/${encodeURIComponent(grantId)}/revoke?reason=${encodeURIComponent(reason)}`),

  receipt: (id: string) => get<PublicReceipt>(`/api/receipts/${encodeURIComponent(id)}`),
  proveRow: (body: {
    grant_id: string; record_id: string; row_index: number;
    field_name: string; receipt_id: string;
  }) => post<RowProof>('/api/verify', body),

  seals: () => get<PeriodSeal[]>('/api/seals'),
  sealPeriod: (body: {
    site: string; record_type: string; period: string; record_ids: string[];
  }) => post<{ response: unknown; tx_id: string; block: number }>('/api/seals', body),
  reopenSeal: (bucket: string, reason: string) =>
    post(`/api/seals/${encodeURIComponent(bucket)}/reopen`, { reason }),
  amendSeal: (bucket: string, addedRecordIds: string[], reason: string) =>
    post(`/api/seals/${encodeURIComponent(bucket)}/amend`,
      { added_record_ids: addedRecordIds, reason }),

  completeness: (body: {
    owner_msp: string; site: string; record_type: string; period: string;
    disclosed_record_ids: string[];
  }) => post<Completeness>('/api/completeness', body),

  plannedWitness: (recordId: string, recordType: string) =>
    get<WitnessRequirement>(
      `/api/witness/requirement?record_id=${encodeURIComponent(recordId)}`
      + `&record_type=${encodeURIComponent(recordType)}`,
    ),
  witnessRequirement: (recordId: string) =>
    get<WitnessRequirement>(`/api/records/${encodeURIComponent(recordId)}/witness-requirement`),

  anchorState: () => get<AnchorState>('/api/anchor/state'),
  anchorGroup: () => get<AnchorGroup>('/api/anchor/group'),
  epochs: () => get<Epoch[]>('/api/anchor/epochs'),
  verifyRecord: (recordId: string, merkleRoot?: string) =>
    post<Verification>(`/api/records/${encodeURIComponent(recordId)}/verify`,
      merkleRoot ? { merkle_root: merkleRoot } : {}),
  publishBeacon: (epoch: number, iterations: number) =>
    post<{
      response: { epoch: number; iterations: number; verified: boolean };
      tx_id: string;
      block: number;
    }>('/api/anchor/beacon', { epoch, iterations }),
  seedRound: (roundId: string) =>
    get<SeedRound>(`/api/seed-rounds/${encodeURIComponent(roundId)}`),
  notifications: () => get<Notification[]>('/api/notifications'),

  nonMembership: (reference: string) =>
    post<Absence>('/api/anchor/non-membership', { reference }),

  registry: () => get<ModelVersion[]>('/api/model/registry'),
  currentModel: () => get<ModelVersion | null>('/api/model/current'),
  rounds: () => get<TrainingRound[]>('/api/model/rounds'),
  benchmarks: () => get<Benchmark[]>('/api/model/benchmarks'),
  decision: (candidateId: string) =>
    get<GateDecision>(`/api/model/decisions/${encodeURIComponent(candidateId)}`),
  memoryBank: () => get<MemoryBank>('/api/model/memory-bank'),
  highWater: () => get<HighWater>('/api/model/high-water'),
  detector: () => get<DetectorStatus>('/api/model/detector'),
  screen: (recordId: string) =>
    post<Screening>(`/api/records/${encodeURIComponent(recordId)}/screen`),

  proposals: () => get<Proposal[]>('/api/governance/proposals'),
  endorse: (id: string) =>
    post<{ proposal_id: string; endorsements: number; required: number; status: string }>(
      `/api/governance/proposals/${encodeURIComponent(id)}/endorse`,
    ),

  requests: () => get<AccessRequest[]>('/api/requests'),
  ask: (body: {
    supplier_msp: string; record_type: string; period: string;
    purpose_code: string; field_name: string; item_reference?: string | null;
    expires_at: string;
  }) => post<{ id: string; status: string }>('/api/requests', body),
  answerRequest: (id: string, recordId: string) =>
    post<{ id: string; status: string; grant_id: string }>(
      `/api/requests/${encodeURIComponent(id)}/grant`, { record_id: recordId },
    ),
  declineRequest: (id: string, reason?: string) =>
    post<{ id: string; status: string }>(
      `/api/requests/${encodeURIComponent(id)}/decline`, { reason },
    ),

  sla: () => get<Sla>('/api/ops/sla'),
  regulatorOverview: () => get<RegulatorOverview>('/api/regulator/overview'),
  auditQueue: () => get<AuditQueue>('/api/audit/queue'),
  attest: (body: { claim_code: string; evidence_scope: string; statement: string }) =>
    post<{ id: string; status: string; signed_at: string }>('/api/attestations', body),

  channels: () => get<Channel[]>('/api/ledger/channels'),
  blocks: (channel: string, limit = 25, offset = 0) =>
    get<Block[]>(`/api/ledger/blocks?channel=${encodeURIComponent(channel)}&limit=${limit}&offset=${offset}`),
  verifyChain: () => get<{ ok: boolean; channels: Channel[] }>('/api/ledger/verify'),
};

/* -- display helpers ------------------------------------------------------ */
/*
 * Record types the ledger accepts, in the words the interface uses.
 *
 * This map is also what the record-type dropdowns offer, so it is a claim about
 * what the contract will take. The authority is `VALID_TYPES` in
 * `model/chaincode/doccustody.py`; anything listed here and missing there is
 * offered to the user and then refused on commit with a bare `unknown record
 * type` rejection, which reads as a broken app rather than a rule.
 *
 * `production_output` was listed here and was never in `VALID_TYPES`. The
 * corpus does generate it — the backend counts those documents, excludes them,
 * and says so on `/api/health` — but no version of the contract has accepted
 * one, so the option could only ever end in a refusal. A type belongs here
 * after the chaincode takes it, not before.
 */
export const RECORD_LABEL: Record<string, string> = {
  payroll_register: 'Payroll Register',
  safety_inspection: 'Safety Inspection',
  chemical_inventory: 'Chemical Inventory',
  machine_maintenance: 'Machine Maintenance',
  compliance_certificate: 'Compliance Certificate',
};

/** The detector's tasks, in the words the interface uses. */
export const TASK_LABEL: Record<string, string> = {
  wage_register_inconsistency: 'Wage-register inconsistency',
  forged_certificate: 'Forged compliance certificate',
  chemical_misreporting: 'Chemical-inventory misreporting',
};

export const taskLabel = (t: string): string =>
  TASK_LABEL[t] ?? t.replace(/_/g, ' ');

export const recordLabel = (t: string): string =>
  RECORD_LABEL[t] ?? t.replace(/_/g, ' ');

/** "ApexTextileMSP" → "Apex Textile" when the directory has not loaded yet. */
export const shortMsp = (msp: string): string =>
  msp.replace(/MSP$/, '').replace(/([a-z])([A-Z])/g, '$1 $2');
