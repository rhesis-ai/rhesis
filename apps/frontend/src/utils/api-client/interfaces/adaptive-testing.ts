/**
 * Interfaces for adaptive testing API.
 * Matches the backend schemas in apps/backend/src/rhesis/backend/app/schemas/adaptive_testing.py
 */

// =============================================================================
// Test Node Interfaces
// =============================================================================

export interface TestNode {
  id: string;
  topic: string;
  input: string;
  output: string;
  label: '' | 'pass' | 'fail';
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
  deleted_ids: string[];
  count: number;
}

export interface DeleteTestResponse {
  deleted: boolean;
  test_id: string;
}
