/**
 * Telemetry API interfaces matching backend schemas
 * from apps/backend/src/rhesis/backend/app/schemas/telemetry.py
 */

/** Span event with known structure from OpenTelemetry */
export interface SpanEvent {
  name: string;
  timestamp?: string;
  attributes?: Record<string, string | number | boolean>;
  [key: string]: unknown;
}

/**
 * Review types for trace reviews (mirroring test-results review types)
 */
export const TRACE_REVIEW_TARGET_TYPES = {
  TRACE: 'trace',
  METRIC: 'metric',
  TURN: 'turn',
} as const;

export type TraceReviewTargetType =
  (typeof TRACE_REVIEW_TARGET_TYPES)[keyof typeof TRACE_REVIEW_TARGET_TYPES];

/** Display labels for review target types (shared across trace components). */
export const TRACE_REVIEW_TARGET_LABELS: Record<
  TraceReviewTargetType | 'test_result',
  string
> = {
  [TRACE_REVIEW_TARGET_TYPES.TRACE]: 'Trace',
  [TRACE_REVIEW_TARGET_TYPES.METRIC]: 'Metric',
  [TRACE_REVIEW_TARGET_TYPES.TURN]: 'Turn',
  test_result: 'Trace',
};

export interface TraceReviewTarget {
  type: TraceReviewTargetType;
  reference: string | null;
}

export interface TraceReviewUser {
  user_id: string;
  name: string;
}

export interface TraceReviewStatus {
  status_id: string;
  name: string;
}

export interface TraceReview {
  review_id: string;
  status: TraceReviewStatus;
  user: TraceReviewUser;
  comments: string;
  created_at: string;
  updated_at: string;
  target: TraceReviewTarget;
}

export interface TraceReviewsMetadata {
  last_updated_at: string;
  last_updated_by: TraceReviewUser;
  total_reviews: number;
  latest_status: TraceReviewStatus;
  summary?: string;
}

export interface TraceReviews {
  metadata: TraceReviewsMetadata;
  reviews: TraceReview[];
}

export interface TraceReviewSummaryEntry {
  target_type: string;
  reference: string | null;
  status: TraceReviewStatus;
  user: TraceReviewUser;
  updated_at: string;
  review_id: string;
}

/**
 * Span node in trace tree with hierarchical children
 */
export interface SpanNode {
  id?: string;
  span_id: string;
  span_name: string;
  span_kind: string;
  start_time: string;
  end_time: string;
  duration_ms: number;
  status_code: string;
  status_message?: string;
  attributes: Record<string, string | number | boolean>;
  events: SpanEvent[];
  children: SpanNode[];
  trace_metrics?: Record<string, unknown>;
  trace_reviews?: TraceReviews;
  last_review?: TraceReview;
  matches_review?: boolean;
  review_summary?: Record<string, TraceReviewSummaryEntry>;
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
  conversation_id?: string;
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

  // Trace metrics evaluation
  trace_metrics_status?: TraceMetricsStatus;

  // Human reviews
  has_reviews?: boolean;
  last_review?: TraceReview;
  matches_review?: boolean;

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
  conversation_id?: string;
  start_time: string;
  end_time: string;
  duration_ms: number;
  span_count: number;
  error_count: number;
  total_tokens: number;
  total_cost_usd: number;
  root_spans: SpanNode[];

  // Trace metrics evaluation
  trace_metrics_status?: TraceMetricsStatus;

  // Human reviews
  trace_reviews?: TraceReviews;
  last_review?: TraceReview;
  matches_review?: boolean;
  review_summary?: Record<string, TraceReviewSummaryEntry>;

  // Related entities (optional - populated via relationships)
  project?: {
    id: string;
    name: string;
    description?: string;
  };
  endpoint?: {
    id: string;
    name: string;
    description?: string;
    url?: string;
    environment?: string;
  };
  test_run?: {
    id: string;
    name?: string;
    nano_id?: string;
    status_id?: string;
  };
  test_result?: {
    id: string;
    test_id?: string;
    test_run_id?: string;
  };
  test?: {
    id: string;
    nano_id?: string;
    test_configuration?: Record<string, unknown>;
  };
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
 * Trace type filter enum (single-turn vs multi-turn)
 */
export type TraceType = 'all' | 'single_turn' | 'multi_turn';

/**
 * Evaluation status for trace metrics (Pass/Fail/Error)
 */
export type TraceMetricsStatus = 'Pass' | 'Fail' | 'Error';

export const TRACE_METRICS_STATUS = {
  PASS: 'Pass' as const,
  FAIL: 'Fail' as const,
  ERROR: 'Error' as const,
};

/**
 * Query parameters for list endpoint
 */
export interface TraceQueryParams {
  project_id?: string; // Optional - shows all projects if not specified
  conversation_id?: string;
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
  trace_type?: TraceType; // Filter by trace type (all/single_turn/multi_turn)
  trace_metrics_status?: TraceMetricsStatus;
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
