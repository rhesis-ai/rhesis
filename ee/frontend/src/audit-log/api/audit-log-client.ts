/**
 * Audit log API client.
 *
 * URL surface: `ee/backend/src/rhesis/backend/ee/audit/router.py`. Every call
 * is gated on `FeatureName.AUDIT_LOG` (404 without it) and on
 * `audit_log:read` unless its comment names another capability.
 * Listing and reading an event record `audit_log.viewed` on the server.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import type {
  PaginatedResponse,
  PaginationParams,
} from '@/utils/api-client/interfaces/pagination';
import type {
  AuditAction,
  AuditEvent,
  AuditEventDetail,
  AuditExportCreate,
  AuditExportCreated,
  AuditLogSettings,
  AuditLogSettingsUpdate,
} from '../types';

export const AUDIT_EVENTS_PATH = '/audit-events';
/** The API's page cap (`limit` le 100). */
export const AUDIT_EVENTS_MAX_LIMIT = 100;
export const AUDIT_EVENTS_SORT_FIELD = 'occurred_at';

export class AuditLogClient extends BaseApiClient {
  async listEvents(
    params: Partial<PaginationParams> = {}
  ): Promise<PaginatedResponse<AuditEvent>> {
    const {
      skip = 0,
      limit = 25,
      sort_by = AUDIT_EVENTS_SORT_FIELD,
      sort_order = 'desc',
      $filter,
    } = params;
    return this.fetchPaginated<AuditEvent>(
      AUDIT_EVENTS_PATH,
      {
        skip,
        limit: Math.min(limit, AUDIT_EVENTS_MAX_LIMIT),
        sort_by,
        sort_order,
        $filter,
      },
      { cache: 'no-store' }
    );
  }

  async getEvent(eventId: string): Promise<AuditEventDetail> {
    return this.fetch<AuditEventDetail>(
      `${AUDIT_EVENTS_PATH}/${encodeURIComponent(eventId)}`,
      { cache: 'no-store' }
    );
  }

  async listActions(): Promise<AuditAction[]> {
    return this.fetch<AuditAction[]>(`${AUDIT_EVENTS_PATH}/actions`);
  }

  /** Needs `audit_log:read`. */
  async getSettings(): Promise<AuditLogSettings> {
    return this.fetch<AuditLogSettings>(`${AUDIT_EVENTS_PATH}/settings`, {
      cache: 'no-store',
    });
  }

  /** Needs `audit_log:manage`. 422 when the retention is above the plan's cap. */
  async updateSettings(
    update: AuditLogSettingsUpdate
  ): Promise<AuditLogSettings> {
    return this.fetch<AuditLogSettings>(`${AUDIT_EVENTS_PATH}/settings`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    });
  }

  /** Needs `audit_log:export`. Starts a job; the file comes later. */
  async createExport(body: AuditExportCreate): Promise<AuditExportCreated> {
    return this.fetch<AuditExportCreated>(`${AUDIT_EVENTS_PATH}/exports`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /**
   * Where the browser downloads a finished export. Opened as a navigation,
   * not fetched: the backend answers with a redirect to a short-lived storage
   * link (another origin, so a fetch would hit CORS) or streams the file.
   * Every request records a download, so it must be made once.
   */
  exportDownloadUrl(jobId: string): string {
    return `${this.baseUrl}${AUDIT_EVENTS_PATH}/exports/${encodeURIComponent(jobId)}/download`;
  }
}
