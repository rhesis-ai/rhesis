import { BaseApiClient } from '@/utils/api-client/base-client';
import { API_ENDPOINTS } from '@/utils/api-client/config';
import type { ReportAuditEntry } from './types';

/** `GET /reports/{id}/audit-trail`: gated on `audit_log` and `report:read`. */
export class ReportAuditClient extends BaseApiClient {
  async getAuditTrail(reportId: string): Promise<ReportAuditEntry[]> {
    return this.fetch<ReportAuditEntry[]>(
      `${API_ENDPOINTS.reports}/${reportId}/audit-trail`,
      { cache: 'no-store' }
    );
  }
}
