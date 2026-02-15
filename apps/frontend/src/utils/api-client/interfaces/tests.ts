import { UUID } from 'crypto';
import { Prompt } from './prompt';
import { Tag } from './tag';
import { Source } from './source';

// Priority level enum
export type PriorityLevel = 'Low' | 'Medium' | 'High' | 'Urgent';

// Base interfaces for related entities
export interface UserReference {
  id: UUID;
  name?: string;
  given_name?: string;
  family_name?: string;
  email?: string;
  picture?: string;
}

export interface TypeLookup {
  id: UUID;
  type_name: string;
  type_value: string;
  description?: string;
}

export interface Topic {
  id: UUID;
  name: string;
  description?: string;
}

export interface Status {
  id: UUID;
  name: string;
  description?: string;
}

export interface Behavior {
  id: UUID;
  nano_id?: string;
  name: string;
  description?: string;
  user_id?: UUID;
  organization_id?: UUID;
  status_id?: UUID;
  counts?: {
    comments: number;
    tasks: number;
  };
}

export interface Category {
  id: UUID;
  name: string;
  description?: string;
}

export interface Organization {
  id: UUID;
  name: string;
  description?: string;
  email?: string;
}

// Test interfaces
export interface TestBase {
  prompt_id: UUID;
  test_type_id?: UUID;
  priority?: number;
  user_id?: UUID;
  assignee_id?: UUID | null;
  owner_id?: UUID | null;
  test_configuration?: Record<string, unknown>;
  parent_id?: UUID;
  topic_id?: UUID;
  behavior_id?: UUID;
  category_id?: UUID;
  status_id?: UUID | null;
  organization_id?: UUID;
  tags?: Tag[];
  test_metadata?: Record<string, unknown>;
}

export type TestCreate = TestBase;

export type TestUpdate = Partial<TestBase>;

export interface Test extends TestBase {
  id: UUID;
  created_at: string;
  updated_at: string;
}

export interface TestDetail extends Test {
  prompt?: Prompt;
  test_type?: TypeLookup;
  user?: UserReference;
  assignee?: UserReference;
  owner?: UserReference;
  parent?: TestDetail;
  topic?: Topic;
  behavior?: Behavior;
  category?: Category;
  status?: Status;
  source?: Source;
  organization?: Organization;
  priorityLevel?: PriorityLevel;
  counts?: {
    comments: number;
    tasks: number;
  };
}

// Test Stats interfaces
export interface TestStatsDimensionBreakdown {
  dimension: string;
  total: number;
  breakdown: Record<string, number>;
}

export interface TestStatsHistorical {
  period: string;
  start_date: string;
  end_date: string;
  monthly_counts: Record<string, number>;
}

export interface TestStats {
  total: number;
  stats: {
    user: TestStatsDimensionBreakdown;
    assignee: TestStatsDimensionBreakdown;
    owner: TestStatsDimensionBreakdown;
    topic: TestStatsDimensionBreakdown;
    behavior: TestStatsDimensionBreakdown;
    category: TestStatsDimensionBreakdown;
    status: TestStatsDimensionBreakdown;
    organization: TestStatsDimensionBreakdown;
    priority: TestStatsDimensionBreakdown;
    [key: string]: TestStatsDimensionBreakdown;
  };
  metadata: {
    generated_at: string;
    organization_id: UUID;
    entity_type: string;
  };
  history?: TestStatsHistorical;
}

// Bulk creation interfaces
export interface TestPromptCreate {
  content: string;
  language_code?: string;
  demographic?: string;
  dimension?: string;
  expected_response?: string;
}

export interface TestBulkCreate {
  prompt?: TestPromptCreate; // Optional - only required for single-turn tests
  behavior: string;
  category: string;
  topic: string;
  test_configuration?: Record<string, unknown>; // Required for multi-turn tests (must contain 'goal')
  assignee_id?: UUID;
  owner_id?: UUID;
  status?: string;
  priority?: number;
}

export interface TestBulkCreateRequest {
  tests: TestBulkCreate[];
  test_set_id?: UUID;
}

export interface TestBulkCreateResponse {
  success: boolean;
  total_tests: number;
  message: string;
}

export interface TestBulkResponse {
  id: UUID;
  prompt_id: UUID;
  test_type_id: UUID;
  priority: number;
  user_id: UUID;
  topic_id: UUID;
  behavior_id: UUID;
  category_id: UUID;
  status_id: UUID;
  organization_id: UUID;
  test_configuration?: Record<string, unknown>;
  prompt?: Record<string, unknown>;
}

// Test execution interfaces
export interface TestExecuteRequest {
  // Option 1: Use existing test
  test_id?: UUID;

  // Required: Endpoint to execute against
  endpoint_id: UUID;

  // Optional: Control metric evaluation
  evaluate_metrics?: boolean;

  // Option 2: Define test inline (required if test_id not provided)
  // For single-turn tests
  prompt?: TestPromptCreate;

  // For multi-turn tests
  test_configuration?: Record<string, unknown>;

  // Required metadata if test_id not provided
  behavior?: string;
  topic?: string;
  category?: string;

  // Optional: Explicitly specify test type (otherwise auto-detected)
  test_type?: 'Single-Turn' | 'Multi-Turn';
}

export interface TestExecuteResponse {
  test_id: string;
  prompt_id?: string;
  execution_time: number; // Milliseconds
  test_output?: string | Record<string, unknown>; // Always returned
  test_metrics?: Record<string, unknown>; // Only if evaluate_metrics=True
  status: 'Pass' | 'Fail' | 'Error' | 'Pending'; // Status
  test_configuration?: Record<string, unknown>; // For multi-turn tests
}

// Conversation-to-test interfaces
export interface ConversationMessage {
  role: string;
  content: string;
}

export interface ConversationToTestRequest {
  messages: ConversationMessage[];
  endpoint_id?: string;
  test_type?: 'Single-Turn' | 'Multi-Turn';
}

export interface ConversationToTestResponse {
  test_id: string;
  message: string;
}

export interface ConversationTestExtractionResponse {
  test_type: 'Single-Turn' | 'Multi-Turn';
  behavior: string;
  category: string;
  topic: string;
  prompt_content?: string;
  expected_response?: string;
  test_configuration?: Record<string, unknown>;
}
