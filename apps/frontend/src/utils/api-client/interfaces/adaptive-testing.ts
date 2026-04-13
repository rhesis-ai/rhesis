/**
 * Interfaces for adaptive testing API.
 * Matches the backend schemas in apps/backend/src/rhesis/backend/app/schemas/adaptive_testing.py
 */

// =============================================================================
// Adaptive Test Set Interface
// =============================================================================

export interface AdaptiveTestSet {
  id: string;
  name: string;
  description?: string;
  slug?: string;
  nano_id?: string;
  status_id?: string;
  status?: string;
  test_set_type_id?: string;
  attributes?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

/** Response from POST /adaptive_testing/import/{source_test_set_id} */
export interface ImportAdaptiveTestSetResponse {
  test_set: AdaptiveTestSet;
  imported: number;
  skipped: number;
  skipped_test_ids: string[];
}

/** Response from POST /adaptive_testing/export/{source_test_set_id} */
export interface ExportAdaptiveTestSetResponse {
  test_set: AdaptiveTestSet;
  exported: number;
  skipped: number;
  skipped_test_ids: string[];
}

// =============================================================================
// Test Node Interfaces
// =============================================================================

/** Per-metric evaluation row (tree/API key is metric name). */
export interface AdaptiveMetricEvalDetail {
  score: number;
  is_successful: boolean;
  reason?: string | null;
  details?: Record<string, unknown> | null;
}

export interface TestNode {
  id: string;
  topic: string;
  input: string;
  output: string;
  label: '' | 'topic_marker' | 'pass' | 'fail';
  labeler: string;
  to_eval: boolean;
  model_score: number;
  metrics?: Record<string, AdaptiveMetricEvalDetail> | null;
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
// Tree Interfaces
// =============================================================================

export interface TreeValidation {
  valid: boolean;
  missing_markers: string[];
  topics_with_tests: string[];
  topics_with_markers: string[];
}

export interface TreeStats {
  total_tests: number;
  total_topics: number;
  tests_by_topic: Record<string, number>;
}

// =============================================================================
// Response Interfaces
// =============================================================================

export interface DeleteTopicResponse {
  deleted: boolean;
  topic_path: string;
}

export interface DeleteTestResponse {
  deleted: boolean;
  test_id: string;
}

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

export interface GenerateOutputsUpdatedItem {
  test_id: string;
  output: string;
}

export interface GenerateOutputsFailedItem {
  test_id: string;
  error: string;
}

export interface GenerateOutputsResponse {
  generated: number;
  skipped: number;
  failed: GenerateOutputsFailedItem[];
  updated: GenerateOutputsUpdatedItem[];
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

export interface EvaluateResultItem {
  test_id: string;
  label: string;
  labeler: string;
  model_score: number;
  metrics?: Record<string, AdaptiveMetricEvalDetail> | null;
}

export interface EvaluateFailedItem {
  test_id: string;
  error: string;
}

export interface EvaluateResponse {
  evaluated: number;
  skipped: number;
  results: EvaluateResultItem[];
  failed: EvaluateFailedItem[];
}

// =============================================================================
// Generate Suggestions
// =============================================================================

export interface GenerateSuggestionsRequest {
  topic?: string | null;
  num_examples?: number;
  num_suggestions?: number;
  user_feedback?: string | null;
  /** When true, API returns embedding vectors per suggestion input (not saved) */
  generate_embeddings?: boolean;
}

export interface SuggestedTest {
  topic: string;
  input: string;
  output: string;
  label: string;
  labeler: string;
  model_score: number;
  embedding?: number[] | null;
  /** Euclidean distance from centroid when generate_embeddings was true */
  diversity_score?: number | null;
}

export interface GenerateSuggestionsResponse {
  suggestions: SuggestedTest[];
  num_examples_used: number;
}

// =============================================================================
// Generate Suggestion Outputs (non-persisted)
// =============================================================================

export interface SuggestionInput {
  input: string;
  topic?: string;
}

export interface GenerateSuggestionOutputsRequest {
  endpoint_id?: string | null;
  suggestions: SuggestionInput[];
}

export interface SuggestionOutputItem {
  input: string;
  output: string;
  error?: string | null;
}

export interface GenerateSuggestionOutputsResponse {
  generated: number;
  results: SuggestionOutputItem[];
}

export interface SuggestionOutputStreamItemEvent {
  type: 'item';
  index: number;
  input: string;
  output: string;
  error: string | null;
}

export interface SuggestionOutputStreamSummaryEvent {
  type: 'summary';
  generated: number;
  total: number;
}

export type SuggestionOutputStreamEvent =
  | SuggestionOutputStreamItemEvent
  | SuggestionOutputStreamSummaryEvent;

// =============================================================================
// Evaluate Suggestions (non-persisted)
// =============================================================================

export interface SuggestionForEval {
  input: string;
  output: string;
}

export interface EvaluateSuggestionsRequest {
  metric_names?: string[] | null;
  suggestions: SuggestionForEval[];
}

export interface SuggestionEvalStreamItemEvent {
  type: 'item';
  index: number;
  input: string;
  label: string;
  labeler: string;
  model_score: number;
  metrics?: Record<string, AdaptiveMetricEvalDetail> | null;
  error: string | null;
}

export interface SuggestionEvalStreamSummaryEvent {
  type: 'summary';
  evaluated: number;
  total: number;
}

export type SuggestionEvalStreamEvent =
  | SuggestionEvalStreamItemEvent
  | SuggestionEvalStreamSummaryEvent;

// =============================================================================
// Adaptive Settings
// =============================================================================

export interface AdaptiveSettingsMetric {
  id: string;
  name: string;
}

export interface AdaptiveSettingsEndpoint {
  id: string;
  name: string;
}

export interface AdaptiveSettings {
  default_endpoint: AdaptiveSettingsEndpoint | null;
  metrics: AdaptiveSettingsMetric[];
}

export interface AdaptiveSettingsUpdateRequest {
  default_endpoint_id?: string | null;
  metric_ids?: string[] | null;
}

export interface SuggestionEvalItem {
  input: string;
  label: string;
  labeler: string;
  model_score: number;
  metrics?: Record<string, AdaptiveMetricEvalDetail> | null;
  error?: string | null;
}

export interface EvaluateSuggestionsResponse {
  evaluated: number;
  results: SuggestionEvalItem[];
}
