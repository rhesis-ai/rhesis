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

// =============================================================================
// Test Node Interfaces
// =============================================================================

export interface TestNode {
  id: string;
  topic: string;
  input: string;
  output: string;
  label: '' | 'topic_marker' | 'pass' | 'fail';
  labeler: string;
  to_eval: boolean;
  model_score: number;
}

export interface TestNodeCreate {
  topic?: string;
  input?: string;
  output?: string;
  label?: '' | 'pass' | 'fail';
  labeler?: string;
  to_eval?: boolean;
  model_score?: number;
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
  endpoint_id: string;
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
  metric_names: string[];
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
}

export interface SuggestedTest {
  topic: string;
  input: string;
  output: string;
  label: string;
  labeler: string;
  model_score: number;
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
  endpoint_id: string;
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

// =============================================================================
// Evaluate Suggestions (non-persisted)
// =============================================================================

export interface SuggestionForEval {
  input: string;
  output: string;
}

export interface EvaluateSuggestionsRequest {
  metric_names: string[];
  suggestions: SuggestionForEval[];
}

export interface SuggestionEvalItem {
  input: string;
  label: string;
  labeler: string;
  model_score: number;
  error?: string | null;
}

export interface EvaluateSuggestionsResponse {
  evaluated: number;
  results: SuggestionEvalItem[];
}
