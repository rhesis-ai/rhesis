/**
 * Telemetry API interfaces matching backend schemas
 * from apps/backend/src/rhesis/backend/app/schemas/telemetry.py
 */

/**
 * Span node in trace tree with hierarchical children
 */
export interface SpanNode {
  span_id: string;
  span_name: string;
  span_kind: string;
  start_time: string;
  end_time: string;
  duration_ms: number;
  status_code: string;
  status_message?: string;
  attributes: Record<string, any>;
  events: Array<Record<string, any>>;
  children: SpanNode[];
  tags?: Array<{ id: string; name: string }>;
  comments?: Array<{ id: string; content: string }>;
}

/**
 * Trace summary for list view
 */
export interface TraceSummary {
  trace_id: string;
  project_id: string;
  environment: string;
  start_time: string;
  duration_ms: number;
  span_count: number;
  root_operation: string;
  status_code: string;
  total_tokens?: number;
  total_cost_usd?: number;
  total_cost_eur?: number;
  has_errors: boolean;

  // Test execution context (optional)
  test_run_id?: string;
  test_result_id?: string;
  test_id?: string;

  // Endpoint information (optional)
  endpoint_id?: string;
  endpoint_name?: string;

  // Counts for UI
  tags_count?: number;
  comments_count?: number;
}

/**
 * Detailed trace response with full span tree
 */
export interface TraceDetailResponse {
  trace_id: string;
  project_id: string;
  environment: string;
  start_time: string;
  end_time: string;
  duration_ms: number;
  span_count: number;
  error_count: number;
  total_tokens: number;
  total_cost_usd: number;
  root_spans: SpanNode[];
}

/**
 * Paginated list response
 */
export interface TraceListResponse {
  traces: TraceSummary[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Trace source filter enum
 */
export type TraceSource = 'all' | 'test' | 'operation';

/**
 * Query parameters for list endpoint
 */
export interface TraceQueryParams {
  project_id?: string; // Optional - shows all projects if not specified
  environment?: string;
  span_name?: string;
  status_code?: string;
  start_time_after?: string;
  start_time_before?: string;
  duration_min_ms?: number; // Minimum duration in milliseconds
  duration_max_ms?: number; // Maximum duration in milliseconds
  test_run_id?: string;
  test_result_id?: string;
  test_id?: string;
  endpoint_id?: string; // Filter by endpoint ID
  trace_source?: TraceSource; // Filter by trace source (all/test/operation)
  root_spans_only?: boolean; // Return only root spans (defaults to true in backend)
  limit?: number;
  offset?: number;
}

/**
 * Aggregated metrics response
 */
export interface TraceMetricsResponse {
  total_traces: number;
  total_spans: number;
  total_tokens: number;
  total_cost_usd: number;
  error_rate: number;
  avg_duration_ms: number;
  p50_duration_ms: number;
  p95_duration_ms: number;
  p99_duration_ms: number;
  operation_breakdown: Record<string, number>;
}
