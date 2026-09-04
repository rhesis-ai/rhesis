/**
 * Telemetry API interfaces matching backend schemas
 * from apps/backend/src/rhesis/backend/app/schemas/telemetry.py
 */

import type { WithPermittedActions } from '@/types/affordances';
import type { Execution, Verdict } from '@/constants/outcomes';

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
  name: string;
}

export interface TraceReviewStatus {
  name: string;
}

export interface TraceReview extends WithPermittedActions {
  review_id: string;
  status: TraceReviewStatus;
  user: TraceReviewUser;
  comments: string;
  created_at: string;
  updated_at: string;
  target: TraceReviewTarget;
  resolved?: boolean;
}

export interface TraceReviews {
  reviews: TraceReview[];
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
  /** Priced by enrichment; absent until a trace has been enriched. */
  cost_usd?: number | null;
  model_name?: string | null;
  events: SpanEvent[];
  children: SpanNode[];
  trace_metrics?: Record<string, unknown>;
  execution: Execution;
  verdict: Verdict | null;
  trace_reviews?: TraceReviews;
  last_review?: TraceReview;
}

/**
 * Trace summary for list view
 */
export interface TraceSummary {
  trace_id: string;
  project_id: string;
  environment: string;
  conversation_id?: string;
  conversation_input?: string;
  start_time: string;
  duration_ms: number;
  span_count: number;
  root_operation: string;

  // Token usage and cost. Summed over the trace's llm.invoke spans, so a trace with
  // no LLM spans omits them rather than reporting zero.
  total_tokens?: number | null;
  total_input_tokens?: number | null;
  total_output_tokens?: number | null;
  total_cost_usd?: number | null;

  // Endpoint information (optional)
  endpoint_id?: string;
  endpoint_name?: string;

  // Trace metrics evaluation. execution/verdict are the source of truth
  // (see constants/outcomes.ts); trace_metrics_status is the legacy display
  // name kept alongside them.
  trace_metrics_status?: TraceMetricsStatus;
  execution: Execution;
  verdict: Verdict | null;

  // Human reviews
  has_reviews?: boolean;
  last_review?: TraceReview;
}

/**
 * Detailed trace response with full span tree
 */
export interface TraceDetailResponse {
  trace_id: string;
  environment: string;
  conversation_id?: string;
  duration_ms: number;
  span_count: number;
  error_count: number;

  // Token usage and cost across the trace's llm.invoke spans. The detail endpoint
  // has the whole span set, so unlike TraceSummary it always resolves the split.
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;

  root_spans: SpanNode[];

  // Trace metrics evaluation. execution/verdict are the source of truth
  // (see constants/outcomes.ts); trace_metrics_status is the legacy display
  // name kept alongside them.
  trace_metrics_status?: TraceMetricsStatus;
  execution: Execution;
  verdict: Verdict | null;

  // Related entities (optional - populated via relationships)
  project?: {
    id: string;
    name: string;
  };
  endpoint?: {
    id: string;
    name: string;
  };
  test_run?: {
    id: string;
    name?: string;
    nano_id?: string;
  };
  test_result?: {
    id: string;
  };
  test?: {
    id: string;
    nano_id?: string;
  };
}

/**
 * Paginated list response
 */
export interface TraceListResponse {
  traces: TraceSummary[];
  total: number;
}

/**
 * Trace source filter enum
 */
export type TraceSource = 'all' | 'test' | 'operation';

/**
 * Trace type filter enum (single-turn vs multi-turn)
 */
export type TraceType = 'all' | 'Single-Turn' | 'Multi-Turn';

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
  environment?: string;
  /** Case-insensitive search across trace ID, operations, endpoint metadata, conversation text */
  search?: string;
  start_time_after?: string;
  start_time_before?: string;
  test_run_id?: string;
  test_result_id?: string;
  test_id?: string;
  endpoint_id?: string; // Filter by endpoint ID
  trace_source?: TraceSource; // Filter by trace source (all/test/operation)
  trace_type?: TraceType; // Filter by trace type (all/Single-Turn/Multi-Turn)
  trace_metrics_status?: TraceMetricsStatus;
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
