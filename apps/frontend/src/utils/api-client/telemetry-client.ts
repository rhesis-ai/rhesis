import { BaseApiClient } from './base-client';
import {
  TraceListResponse,
  TraceDetailResponse,
  TraceQueryParams,
  TraceMetricsResponse,
} from './interfaces/telemetry';

/**
 * API client for telemetry/tracing endpoints
 */
export class TelemetryClient extends BaseApiClient {
  /**
   * List traces with filters and pagination
   */
  async listTraces(params: TraceQueryParams): Promise<TraceListResponse> {
    const queryParams = new URLSearchParams();

    // Add all defined parameters to query string
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, value.toString());
      }
    });

    const queryString = queryParams.toString();
    const endpoint = queryString
      ? `/telemetry/traces?${queryString}`
      : '/telemetry/traces';

    return this.fetch<TraceListResponse>(endpoint, {
      cache: 'no-store',
    });
  }

  /**
   * Get detailed trace with all spans
   *
   * Note: project_id is required for access control even though trace_id is unique.
   * The backend enforces organization-level security by filtering on both project_id
   * and organization_id (extracted from auth context) to prevent cross-tenant data access.
   */
  async getTrace(
    traceId: string,
    projectId: string
  ): Promise<TraceDetailResponse> {
    return this.fetch<TraceDetailResponse>(
      `/telemetry/traces/${traceId}?project_id=${projectId}`,
      { cache: 'no-store' }
    );
  }

  /**
   * Get aggregated metrics (for future dashboard use)
   */
  async getMetrics(params: {
    project_id: string;
    environment?: string;
    start_time_after?: string;
    start_time_before?: string;
  }): Promise<TraceMetricsResponse> {
    const queryParams = new URLSearchParams();

    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        queryParams.append(key, value.toString());
      }
    });

    const queryString = queryParams.toString();
    const endpoint = queryString
      ? `/telemetry/metrics?${queryString}`
      : '/telemetry/metrics';

    return this.fetch<TraceMetricsResponse>(endpoint, {
      cache: 'no-store',
    });
  }
}
