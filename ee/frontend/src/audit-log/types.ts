/**
 * Shapes of the audit log read API (`ee/backend/.../ee/audit/schemas.py`).
 */

/** Mirrors `outcome` on the backend's `AuditRecorded`. */
export const AuditOutcome = {
  SUCCESS: 'success',
  FAILURE: 'failure',
  DENIED: 'denied',
} as const;
export type AuditOutcome = (typeof AuditOutcome)[keyof typeof AuditOutcome];

/** Mirrors the backend's `Channel` enum (`app/provenance.py`). */
export const AuditChannel = {
  WEB: 'web',
  SDK: 'sdk',
  MCP: 'mcp',
  ARCHITECT: 'architect',
  API: 'api',
  JOB: 'job',
} as const;
export type AuditChannel = (typeof AuditChannel)[keyof typeof AuditChannel];

/** Mirrors the backend's `ActorType` enum (`app/provenance.py`). */
export const AuditActorType = {
  USER: 'user',
  API_TOKEN: 'api_token',
  API_CLIENT: 'api_client',
  SYSTEM: 'system',
  ANONYMOUS: 'anonymous',
} as const;
export type AuditActorType =
  (typeof AuditActorType)[keyof typeof AuditActorType];

/** Mirrors `FieldChange.kind`: secrets carry no values, content only in `content_changes`. */
export const FieldChangeKind = {
  VALUE: 'value',
  SECRET: 'secret',
  CONTENT: 'content',
} as const;
export type FieldChangeKind =
  (typeof FieldChangeKind)[keyof typeof FieldChangeKind];

export interface FieldChange {
  field: string;
  kind: FieldChangeKind;
  before?: unknown;
  after?: unknown;
}

/** A content field's values, present only while the org includes content. */
export interface ContentChange {
  field: string;
  before?: unknown;
  after?: unknown;
}

/**
 * `changes` is a list of field changes for a row change. Summaries are an
 * object instead: a job's bulk create is `{count, ids}`, a purge
 * `{count, oldest, before}`.
 */
export type AuditChanges = FieldChange[] | Record<string, unknown> | null;

export interface AuditEvent {
  id: string;
  organization_id: string;
  project_id: string | null;
  occurred_at: string;
  recorded_at: string;
  action: string;
  outcome: string;
  status_code: number | null;
  actor_type: string;
  actor_id: string | null;
  actor_credential_id: string | null;
  actor_credential_hint: string | null;
  actor_label: string | null;
  channel: string;
  ip: string | null;
  user_agent: string | null;
  resource_id: string | null;
  resource_label: string | null;
  request_id: string | null;
  trace_id: string;
  span_id: string;
  job_id: string | null;
  changes: AuditChanges;
}

/** A listed event with its project's name, looked up by the table, not the API. */
export interface AuditEventRow extends AuditEvent {
  project_name?: string;
}

export interface AuditEventDetail extends AuditEvent {
  content_changes?: ContentChange[] | null;
}

/** One action the log can hold: `endpoint.updated` is `endpoint` + `updated`. */
export interface AuditAction {
  action: string;
  resource: string;
  verb: string;
}

/** `GET /audit-events/settings` (`AuditLogSettingsRead`). */
export interface AuditLogSettings {
  /** The window in force: the org's choice, capped by its plan. */
  retention_days: number;
  max_retention_days: number;
  /** A warning only: the backend does not enforce it. */
  below_eu_ai_act_minimum: boolean;
  mask_ip: boolean;
  include_content: boolean;
  /** Whether the scheduler's heartbeat is recent; null when the backend cannot tell. */
  scheduled_jobs_running: boolean | null;
}

/** `PATCH /audit-events/settings`: the fields sent change, the rest keep their value. */
export type AuditLogSettingsUpdate = Partial<
  Pick<AuditLogSettings, 'retention_days' | 'mask_ip' | 'include_content'>
>;

/** Mirrors `AuditExportCreate.format`. */
export const AuditExportFormat = {
  JSONL: 'jsonl',
  CSV: 'csv',
} as const;
export type AuditExportFormat =
  (typeof AuditExportFormat)[keyof typeof AuditExportFormat];

export interface AuditExportCreate {
  format: AuditExportFormat;
  /** The list's `$filter`; omitted for the whole log. */
  filter?: string;
}

/** `POST /audit-events/exports` (202). */
export interface AuditExportCreated {
  /** The job row; null if the backend could not record it. */
  job_id: string | null;
  task_id: string;
  format: AuditExportFormat;
  message: string;
}

/** The export job's `job_type` (`export/service.py` `JOB_TYPE`). */
export const AUDIT_EXPORT_JOB_TYPE = 'audit_log.export';
