/*
 * Typed client for the Breadcrumbs API.
 *
 * One rule: every response type here mirrors what the backend actually returns,
 * and the backend returns what the *ledger* recorded. Where a shape looks
 * awkward — per-task rows carrying their own benchmark hash, decisions carrying
 * their rejected submissions — that is the audit trail showing through, and it
 * should not be smoothed away.
 */

const BASE = '/api';

export type Role = 'factory' | 'buyer' | 'auditor' | 'consortium' | 'regulator';

export interface RoleOption {
  role: Role;
  label: string;
  org: string;
  person: string;
  summary: string;
  landing: string;
}

export interface Session {
  access_token: string;
  token_type: string;
  role: Role;
  org: string;
  person: string;
  landing: string;
}

export interface LedgerRecord {
  record_id: string;
  owner_msp: string;
  merkle_root: string;
  record_type: string;
  period: string;
  site: string;
  row_count: number;
  schema_version: string;
  committed_at: string;
  status: 'committed' | 'superseded';
  superseded_by: string | null;
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
  status: 'active' | 'revoked';
  revoked_reason: string | null;
}

export interface ProofStep {
  sibling: string;
  position: 'left' | 'right';
}

export interface VerificationResult {
  verified: boolean;
  verdict: string;
  disclosed: { field_name: string; value: unknown };
  proof: {
    computed_root: string;
    on_chain_root: string;
    match: boolean;
    steps: ProofStep[];
    ladder: string[];
    rows_in_record: number;
    rows_disclosed: number;
  };
  receipt: Record<string, unknown>;
  tx_id: string;
  block: number | null;
}

/** One row of the Continuity Gate's decision table. */
export interface GateTaskRow {
  task_id: string;
  benchmark_hash: string;
  candidate_bp: number;
  previous_bp: number;
  change_bp: number;
  is_new_task: boolean;
  threshold_bp: number;
  pass: boolean;
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
  parameters: { gamma_bp: number; tau_bp: number; k: number; delta_bp: number };
  decided_at: string;
  per_task: GateTaskRow[];
  outcome: 'promote' | 'reject';
  reason_code: string;
  reason: string;
  guarantee?: string;
  tx_id?: string;
  block?: number | null;
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
  per_task: GateTaskRow[];
  decided_at: string;
}

export interface Benchmark {
  task_id: string;
  benchmark_hash: string;
  committed_at: string;
  committed_by: string;
  contributors: string[];
  size: number;
  revealed: boolean;
  revealed_at: string | null;
}

export interface BlockSummary {
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

export interface ChannelSummary {
  channel: string;
  height: number;
  head_hash: string;
  integrity_ok: boolean;
  integrity_detail: string;
  members: string[];
}

const TOKEN_KEY = 'breadcrumbs.session';

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    // A private window or blocked site data. Not an error; just no session.
    return null;
  }
}

export function saveSession(session: Session): void {
  try {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(session));
  } catch {
    /* storage unavailable; the session lives for this page only */
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing to do */
  }
}

/**
 * A refusal that carries the chaincode's own sentence.
 *
 * The interface shows that sentence rather than a generic failure, because
 * "grant covers net_pay_bdt, not national_id" tells the user what to do next
 * and "Request failed" does not.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = loadSession();
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let message = response.statusText;
    let code: string | undefined;
    try {
      const body = await response.json();
      const detail = body.detail ?? body;
      message = typeof detail === 'string' ? detail : (detail.message ?? message);
      code = typeof detail === 'object' ? detail.code : body.code;
    } catch {
      /* keep the status text */
    }
    if (response.status === 401) clearSession();
    throw new ApiError(message, response.status, code);
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });

export const api = {
  roles: () => get<RoleOption[]>('/auth/roles'),
  signIn: (role: Role, code: string) => post<Session>('/auth/verify', { role, code }),
  me: () => get<{ role: Role; org: string; person: string; read_only: boolean }>('/auth/me'),

  records: () => get<LedgerRecord[]>('/records'),
  record: (id: string) =>
    get<{ record: LedgerRecord; receipts: unknown[]; rows_held_off_chain: number }>(
      `/records/${id}`,
    ),
  grants: () => get<Grant[]>('/grants'),
  revokeGrant: (id: string, reason: string) =>
    post(`/grants/${id}/revoke?reason=${encodeURIComponent(reason)}`),
  verifyRow: (body: {
    grant_id: string;
    record_id: string;
    row_index: number;
    field_name: string;
    receipt_id: string;
  }) => post<VerificationResult>('/verify', body),

  currentModel: () => get<ModelVersion | null>('/model/current'),
  registry: () => get<ModelVersion[]>('/model/registry'),
  rounds: () => get<Record<string, unknown>[]>('/model/rounds'),
  benchmarks: () => get<Benchmark[]>('/model/benchmarks'),
  decision: (candidateId: string) => get<GateDecision>(`/model/decisions/${candidateId}`),
  memoryBank: () =>
    get<{ anchored_hashes: unknown[]; privacy_note: string; contains: string }>(
      '/model/memory-bank',
    ),

  proposals: () => get<Record<string, unknown>[]>('/governance/proposals'),
  endorse: (id: string) => post(`/governance/proposals/${id}/endorse`),
  members: () => get<Record<string, unknown>[]>('/governance/members'),
  sla: () => get<Record<string, unknown>>('/ops/sla'),
  notifications: () => get<Record<string, unknown>[]>('/notifications'),
  regulatorOverview: () => get<Record<string, unknown>>('/regulator/overview'),

  channels: () => get<ChannelSummary[]>('/ledger/channels'),
  blocks: (channel: string) =>
    get<BlockSummary[]>(`/ledger/blocks?channel=${encodeURIComponent(channel)}`),
  verifyChain: () => get<{ ok: boolean; channels: ChannelSummary[] }>('/ledger/verify'),

  health: () => get<Record<string, unknown>>('/health'),
};

/** Basis points to a display percentage: 7790 becomes "77.9". */
export const bp = (value: number, digits = 1): string => (value / 100).toFixed(digits);

/** First 12 and last 4 of a hash, per the design specification. */
export const truncateHash = (hash: string): string =>
  hash.length <= 18 ? hash : `${hash.slice(0, 12)}…${hash.slice(-4)}`;
