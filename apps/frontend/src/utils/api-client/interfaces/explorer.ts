/**
 * Interfaces for Explorer (test tree) API.
 * Matches the backend schemas in apps/backend/src/rhesis/backend/app/schemas/explorer.py
 */

import { Status } from './status';
import { UserReference } from './tests';

// =============================================================================
// Explorer test set (TestSet JSON from GET /explorer)
// =============================================================================

/** Bare schemas.TestSet -- what create, detail, import and export return. */
export interface ExplorerTestSet {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
}

/** schemas.TestSetDetail -- only GET /explorer/ expands these relations. */
export interface ExplorerTestSetDetail extends ExplorerTestSet {
  user?: UserReference;
  status?: Status;
}

/** Response from POST /explorer/import/{source_test_set_id} */
export interface ImportExplorerTestSetResponse {
  test_set: ExplorerTestSet;
  imported: number;
  skipped: number;
}

/** Response from POST /explorer/export/{source_test_set_id} */
export interface ExportExplorerTestSetResponse {
  test_set: ExplorerTestSet;
  exported: number;
  skipped: number;
}

// =============================================================================
// Test Node Interfaces
// =============================================================================

/** Per-metric evaluation row (tree/API key is metric name). */
export interface ExplorerMetricEvalDetail {
  reason?: string | null;
  details?: Record<string, unknown> | null;
}

export interface TestNode {
  id: string;
  topic: string;
  input: string;
  output: string;
  /** 'error' is set by the backend when a metric raises during evaluation. */
  label: '' | 'topic_marker' | 'pass' | 'fail' | 'error';
  labeler: string;
  to_eval: boolean;
  model_score: number;
  metrics?: Record<string, ExplorerMetricEvalDetail> | null;
}

export interface TestNodeCreate {
  topic?: string;
  input?: string;
  output?: string;
  label?: '' | 'pass' | 'fail';
  labeler?: string;
  to_eval?: boolean;
  model_score?: number;
  /** When true, backend embeds test input and persists to embedding table */
  generate_embedding?: boolean;
}

export interface TestNodeUpdate {
  topic?: string;
  input?: string;
  output?: string;
  label?: '' | 'pass' | 'fail';
  to_eval?: boolean;
  model_score?: number;
}

// =============================================================================
// Topic Interfaces
// =============================================================================

export interface Topic {
  path: string;
  name: string;
  parent_path: string | null;
  depth: number;
  display_name: string;
  display_path: string;
  has_direct_tests: boolean;
  has_subtopics: boolean;
}

export interface TopicCreate {
  path: string;
  labeler?: string;
}

export interface TopicUpdate {
  new_name?: string;
  new_path?: string;
}

// =============================================================================
// Response Interfaces
// =============================================================================

// =============================================================================
// Generate Outputs
// =============================================================================

export interface GenerateOutputsRequest {
  endpoint_id?: string | null;
  test_ids?: string[] | null;
  topic?: string | null;
  include_subtopics?: boolean;
  overwrite?: boolean;
}

export interface GenerateOutputsResponse {
  generated: number;
  skipped: number;
  failed: unknown[];
}

// =============================================================================
// Evaluate
// =============================================================================

export interface EvaluateRequest {
  metric_names?: string[] | null;
  test_ids?: string[] | null;
  topic?: string | null;
  include_subtopics?: boolean;
  overwrite?: boolean;
}

export interface EvaluateResponse {
  evaluated: number;
  skipped: number;
  failed: unknown[];
}

export interface SuggestedTest {
  topic: string;
  input: string;
  output: string;
  label: string;
  labeler: string;
  model_score: number;
  embedding?: number[] | null;
  /**
   * Centroid-based diversity when generate_embeddings was true (default: 1 − cosine
   * to batch mean direction; higher = more diverse)
   */
  diversity_score?: number | null;
}

// =============================================================================
// Unified Suggestion Pipeline (single stream)
// =============================================================================

export interface SuggestionPipelineRequest {
  topic?: string | null;
  generate_embeddings?: boolean;
  num_examples?: number;
  num_suggestions?: number;
  user_feedback?: string | null;
  endpoint_id?: string | null;
  metric_names?: string[] | null;
}

/** Bulk suggestions event (legacy / non-streaming fallback). */
export interface PipelineSuggestionsEvent {
  type: 'suggestions';
  suggestions: SuggestedTest[];
  num_examples_used: number;
}

/** Streamed: single suggestion parsed from the LLM token stream. */
export interface PipelineSuggestionEvent {
  type: 'suggestion';
  index: number;
  topic: string;
  input: string;
}

/** Streamed: embedding completed for a single suggestion (index only, no vector). */
export interface PipelineEmbeddingEvent {
  type: 'embedding';
  index: number;
}

/** Streamed: all suggestions (and embeddings) are done. */
export interface PipelineSuggestionsDoneEvent {
  type: 'suggestions_done';
  total: number;
  num_examples_used: number;
  diversity_order: number[] | null;
  /** Diversity metric per row in sorted display order (same length as diversity_order). */
  diversity_scores?: (number | null)[] | null;
}

export interface PipelineOutputEvent {
  type: 'output';
  index: number;
  input: string;
  output: string;
  error: string | null;
}

export interface PipelineEvaluationEvent {
  type: 'evaluation';
  index: number;
  input: string;
  label: string;
  labeler: string;
  model_score: number;
  metrics?: Record<string, ExplorerMetricEvalDetail> | null;
  error: string | null;
}

export interface PipelineOutputSummaryEvent {
  type: 'output_summary';
  generated: number;
  total: number;
}

export interface PipelineEvalSummaryEvent {
  type: 'eval_summary';
  evaluated: number;
  total: number;
}

export interface PipelineDoneEvent {
  type: 'done';
}

export type SuggestionPipelineEvent =
  | PipelineSuggestionsEvent
  | PipelineSuggestionEvent
  | PipelineEmbeddingEvent
  | PipelineSuggestionsDoneEvent
  | PipelineOutputEvent
  | PipelineEvaluationEvent
  | PipelineOutputSummaryEvent
  | PipelineEvalSummaryEvent
  | PipelineDoneEvent;

// =============================================================================
// Explorer settings (stored server-side under adaptive_settings)
// =============================================================================

export interface ExplorerSettingsMetric {
  id: string;
  name: string;
}

export interface ExplorerSettingsEndpoint {
  id: string;
  name: string;
}

export interface ExplorerSettings {
  default_endpoint: ExplorerSettingsEndpoint | null;
  metrics: ExplorerSettingsMetric[];
}

export interface ExplorerSettingsUpdateRequest {
  default_endpoint_id?: string | null;
  metric_ids?: string[] | null;
}
