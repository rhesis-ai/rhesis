import { UUID } from 'crypto';
import { Prompt } from './prompt';
import { Tag } from './tag';
import { TestTypeValue } from '@/constants/test-types';

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
  type_value: string;
}

export interface Topic {
  id: UUID;
  name: string;
}

export interface Status {
  id: UUID;
  name: string;
}

export interface Requirement {
  id: UUID;
  name: string;
}

export interface Category {
  id: UUID;
  name: string;
}

// Test interfaces
export interface TestBase {
  prompt_id?: UUID;
  test_type_id?: UUID;
  priority?: number;
  user_id?: UUID;
  assignee_id?: UUID | null;
  owner_id?: UUID | null;
  test_configuration?: Record<string, unknown>;
  parent_id?: UUID;
  topic_id?: UUID;
  requirement_id?: UUID;
  category_id?: UUID;
  status_id?: UUID | null;
  organization_id?: UUID;
  tags?: Tag[];
  test_metadata?: Record<string, unknown>;
}

export interface TestCreate extends TestBase {
  requirement?: string;
  topic?: string;
  category?: string;
  prompt?: TestPromptCreate;
  test_type?: string;
  status?: string;
}

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
  topic?: Topic;
  requirement?: Requirement;
  category?: Category;
  status?: Status;
  priorityLevel?: PriorityLevel;
  counts?: {
    comments?: number;
    tasks?: number;
    files?: number;
  };
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
  requirement: string;
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
  message: string;
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
  requirement?: string;
  topic?: string;
  category?: string;

  // Optional: Explicitly specify test type (otherwise auto-detected)
  test_type?: TestTypeValue;
}

export interface TestExecuteResponse {
  execution_time: number; // Milliseconds
  test_output?: string | Record<string, unknown>; // Always returned
  status: 'Pass' | 'Fail' | 'Error' | 'Pending'; // Status
}

// Conversation-to-test interfaces
export interface ConversationMessage {
  role: string;
  content: string;
}

export interface ConversationToTestRequest {
  messages: ConversationMessage[];
  endpoint_id?: string;
  test_type?: TestTypeValue;
}

export interface ConversationTestExtractionResponse {
  test_type: TestTypeValue;
  requirement: string;
  category: string;
  topic: string;
  prompt_content?: string;
  expected_response?: string;
  test_configuration?: Record<string, unknown>;
}

export interface TestFacets {
  requirements: string[];
  categories: string[];
  topics: string[];
  test_types: string[];
}
