import { BaseApiClient } from './base-client';
import {
  SpanFacetsResponse,
  SpanFilterParams,
  SpanListResponse,
  SpanQueryParams,
  TraceListResponse,
  TraceDetailResponse,
  TraceQueryParams,
  TraceMetricsResponse,
} from './interfaces/telemetry';

/**
 * `path?query` with empty values left out. Arrays are appended one entry at a time:
 * FastAPI reads a repeatable filter as `?provider=a&provider=b`, and the default
 * toString() would send the single value "a,b" instead.
 */
function withQuery(path: string, params: object): string {
  const queryParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) {
      value.forEach(entry => {
        if (entry !== undefined && entry !== null && entry !== '') {
          queryParams.append(key, String(entry));
        }
      });
      return;
    }
    queryParams.append(key, String(value));
  });
  const queryString = queryParams.toString();
  return queryString ? `${path}?${queryString}` : path;
}

/**
 * API client for telemetry/tracing endpoints
 */
export class TelemetryClient extends BaseApiClient {
  /**
   * List traces with filters and pagination
   */
  async listTraces(params: TraceQueryParams): Promise<TraceListResponse> {
    return this.fetch<TraceListResponse>(
      withQuery('/telemetry/traces', params),
      { cache: 'no-store' }
    );
  }

  /**
   * List spans, one row per span, with filters, sorting and pagination.
   */
  async listSpans(params: SpanQueryParams): Promise<SpanListResponse> {
    return this.fetch<SpanListResponse>(withQuery('/telemetry/spans', params), {
      cache: 'no-store',
    });
  }

  /**
   * Span types, names and models with counts under the given filters, for the
   * span filter drawer. Each facet ignores its own filter.
   */
  async getSpanFacets(
    params: SpanFilterParams,
    nameLimit?: number
  ): Promise<SpanFacetsResponse> {
    return this.fetch<SpanFacetsResponse>(
      withQuery('/telemetry/spans/facets', {
        ...params,
        name_limit: nameLimit,
      }),
      { cache: 'no-store' }
    );
  }

  /**
   * LLM providers present in a project's traces, for the traces filter checklist.
   *
   * Comes from the same data the filter matches on, so every value offered returns
   * something.
   */
  async getProviders(projectId?: string): Promise<string[]> {
    const query = projectId
      ? `?project_id=${encodeURIComponent(projectId)}`
      : '';
    return this.fetch<string[]>(`/telemetry/providers${query}`, {
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
    /** Narrows every metric to one test run. */
    test_run_id?: string;
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

  /**
   * Resolve a span DB UUID to its trace_id and project_id.
   * Used for navigating to traces from tasks/comments.
   */
  async lookupSpan(
    spanDbId: string
  ): Promise<{ trace_id: string; project_id: string; span_id: string }> {
    return this.fetch<{
      trace_id: string;
      project_id: string;
      span_id: string;
    }>(`/telemetry/spans/${spanDbId}/lookup`, { cache: 'no-store' });
  }
}
