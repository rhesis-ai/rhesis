import { UUID } from 'crypto';
import { Status } from './status';
import { Tag } from './tag';

// User interface for the nested user data
export interface User {
  name?: string;
  email?: string;
  family_name?: string;
  given_name?: string;
  picture?: string;
}

// TestSetType interface for the nested test_set_type data
export interface TestSetType {
  type_value: string;
}

/**
 * Metric reference for test sets - lightweight representation of associated metrics
 */
export interface TestSetMetric {
  id: UUID;
  name: string;
  description?: string;
  score_type?: 'numeric' | 'categorical';
  threshold?: number;
  threshold_operator?: string;
  backend_type?: {
    type_value: string;
  };
}

export interface TestSet {
  id: UUID;
  name: string;
  description?: string;
  status_id?: UUID;
  status: string | Status;
  status_details?: Status;
  tags?: Tag[];
  test_set_type_id?: UUID;
  test_set_type?: TestSetType;
  attributes?: {
    metadata?: {
      total_tests?: number;
      categories?: string[];
      behaviors?: string[];
      topics?: string[];
      sources?: Array<{ document: string; name: string; description: string }>;
      generation?: {
        status: 'in_progress' | 'completed' | 'failed';
      };
    };
    // Garak-specific attributes
    source?: string;
  };
  user_id?: UUID;
  user?: User;
  priority?: number;
  organization_id?: UUID;
  is_published: boolean;
  counts?: {
    comments: number;
    tasks: number;
  };
  created_at?: string;
}

export interface TestSetCreate {
  name: string;
  description?: string;
  short_description?: string;
  slug?: string;
  status_id?: UUID;
  tags?: string[];
  attributes?: Record<string, unknown>;
  priority?: number;
  test_set_type_id?: UUID;
}

// Test set association request
export interface TestSetBulkAssociateRequest {
  test_ids: UUID[];
}

// Test set generation interfaces

/**
 * GenerationConfig matches the SDK's GenerationConfig structure
 */
export interface GenerationConfig {
  generation_prompt?: string;
  behaviors?: string[];
  categories?: string[];
  topics?: string[];
  additional_context?: string;
}

export interface SourceData {
  id: string;
  name?: string;
  description?: string;
  content?: string;
}

/**
 * Unified request for both sampling (services) and bulk generation (test_sets)
 */
export interface GenerateTestsRequest {
  config: GenerationConfig;
  num_tests: number;
  batch_size?: number;
  sources?: SourceData[];
  name?: string; // Only used for bulk generation
  test_type?: 'Single-Turn' | 'Multi-Turn'; // Type of tests to generate
  model_id?: string; // Override user's default generation model for this request
  project_id?: string; // Required for bulk generation via POST /test_sets/generate
}

/**
 * Response for sampling (synchronous)
 */
export interface GenerateTestsResponse {
  tests: unknown[]; // Test objects
}

/**
 * Response for bulk generation (async via worker)
 */
export interface GenerateTestSetResponse {
  test_set_id: string;
}

// Legacy interfaces - kept for backwards compatibility during migration
/** @deprecated Use GenerationConfig instead */
export interface GenerationSample {
  text: string;
  behavior: string;
  topic: string;
  rating?: number | null;
  feedback?: string;
}

/** @deprecated Use GenerationConfig instead */
export interface TestSetGenerationConfig extends GenerationConfig {
  project_name?: string;
  purposes?: string[];
  test_type?: string;
  response_generation?: string;
  test_coverage?: string;
  tags?: string[];
  description?: string;
}

/** @deprecated Use GenerateTestsRequest instead */
export interface TestSetGenerationRequest extends GenerateTestsRequest {
  samples?: GenerationSample[];
  synthesizer_type?: string;
}

/** @deprecated Use GenerateTestSetResponse instead */
export type TestSetGenerationResponse = GenerateTestSetResponse;

// ── Streaming test pipeline types ──

export interface IterationMessage {
  content: string;
  timestamp: string;
  chip_states?: Array<{
    label: string;
    description: string;
    active: boolean;
    category: string;
  }>;
}

export interface TestPipelineConfig {
  behaviors: Array<{ name: string; description: string; active: boolean }>;
  topics: Array<{ name: string; description: string; active: boolean }>;
  categories: Array<{ name: string; description: string; active: boolean }>;
}

export interface TestPipelineRequest {
  prompt: string;
  project_id?: string;
  previous_messages?: IterationMessage[];
  test_type?: string;
  num_tests?: number;
  sources?: SourceData[];
  model_id?: string;
  config?: TestPipelineConfig;
}

export type TestPipelineEvent =
  | {
      type: 'config_item';
      category: 'behaviors' | 'topics' | 'categories';
      name: string;
      description: string;
      active: boolean;
    }
  | { type: 'config_done' }
  | {
      type: 'test';
      index: number;
      test: Record<string, unknown>;
      test_type: string;
    }
  | { type: 'tests_done' }
  | { type: 'error'; phase: string; message: string }
  | { type: 'done' };

/** Summary of the most recent test run for a test set + endpoint combo. */
export interface LastTestRunSummary {
  id: string;
  nano_id: string | null;
  name: string | null;
  created_at: string | null;
  test_count: number;
  pass_rate: number;
}
