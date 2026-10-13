/**
 * Shapes of the streaming destinations API
 * (`ee/backend/.../ee/audit/streaming/schemas.py`), and how a row reads.
 */

/** Mirrors the backend `KINDS` (`streaming/adapters.py`). */
export const DestinationKind = {
  WEBHOOK: 'webhook',
  SPLUNK_HEC: 'splunk_hec',
  DATADOG: 'datadog',
} as const;
export type DestinationKind =
  (typeof DestinationKind)[keyof typeof DestinationKind];

export const DESTINATION_KIND_LABELS: Record<DestinationKind, string> = {
  webhook: 'Webhook',
  splunk_hec: 'Splunk HEC',
  datadog: 'Datadog',
};

/** Mirrors the backend `DATADOG_SITES`; the API rejects any other value. */
export const DATADOG_SITES = [
  'datadoghq.com',
  'us3.datadoghq.com',
  'us5.datadoghq.com',
  'datadoghq.eu',
  'ap1.datadoghq.com',
  'ap2.datadoghq.com',
  'ddog-gov.com',
] as const;
export type DatadogSite = (typeof DATADOG_SITES)[number];

/** Mirrors the backend `PAUSED_MANUAL` / `PAUSED_FAILURES`. */
export const PausedReason = {
  MANUAL: 'manual',
  FAILURES: 'failures',
} as const;

/** Field limits from the backend schemas. */
export const DESTINATION_LIMITS = {
  NAME: 120,
  URL: 2048,
  SECRET: 512,
} as const;

export const STANDARD_WEBHOOKS_URL = 'https://www.standardwebhooks.com';

export interface AuditDestination {
  id: string;
  name: string;
  kind: string;
  /** The config without its secrets: `url` for webhook and Splunk, `site` for Datadog. */
  settings: Record<string, unknown>;
  paused: boolean;
  paused_reason: string | null;
  /** Events recorded up to here have been delivered. */
  delivered_through: string;
  last_success_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
  consecutive_failures: number;
  next_attempt_at: string | null;
  created_at: string;
}

/** The create response. `signing_secret` is set for webhooks, and only here. */
export interface AuditDestinationCreated extends AuditDestination {
  signing_secret?: string | null;
}

export type AuditDestinationCreate =
  | { kind: typeof DestinationKind.WEBHOOK; name: string; url: string }
  | {
      kind: typeof DestinationKind.SPLUNK_HEC;
      name: string;
      url: string;
      token: string;
    }
  | {
      kind: typeof DestinationKind.DATADOG;
      name: string;
      site: DatadogSite;
      api_key: string;
    };

export interface TestEventResult {
  delivered: boolean;
  error: string | null;
}

export const DestinationStatus = {
  ACTIVE: 'active',
  PAUSED: 'paused',
  AUTO_PAUSED: 'auto_paused',
} as const;
export type DestinationStatus =
  (typeof DestinationStatus)[keyof typeof DestinationStatus];

export function destinationStatus(d: AuditDestination): DestinationStatus {
  if (!d.paused) return DestinationStatus.ACTIVE;
  return d.paused_reason === PausedReason.FAILURES
    ? DestinationStatus.AUTO_PAUSED
    : DestinationStatus.PAUSED;
}

export function kindLabel(kind: string): string {
  return DESTINATION_KIND_LABELS[kind as DestinationKind] ?? kind;
}

/** Where events go: the URL, or the Datadog site. */
export function destinationTarget(d: AuditDestination): string {
  const { url, site } = d.settings;
  if (typeof url === 'string') return url;
  if (typeof site === 'string') return site;
  return '';
}

export function isHttpsUrl(value: string): boolean {
  try {
    return new URL(value).protocol === 'https:';
  } catch {
    return false;
  }
}

/** Drops the one-time secret before the row goes into list state. */
export function withoutSecret(
  created: AuditDestinationCreated
): AuditDestination {
  const { signing_secret: _secret, ...row } = created;
  return row;
}
