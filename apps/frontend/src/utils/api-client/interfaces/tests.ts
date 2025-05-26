import { UUID } from 'crypto';
import { Prompt } from './prompt';
import { Tag } from './tag';

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
  name: string;
  description?: string;
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
  assignee_id?: UUID;
  owner_id?: UUID;
  test_configuration?: Record<string, any>;
  parent_id?: UUID;
  topic_id?: UUID;
  behavior_id?: UUID;
  category_id?: UUID;
  status_id?: UUID;
  organization_id?: UUID;
  tags?: Tag[];
}

export interface TestCreate extends TestBase {}

export interface TestUpdate extends Partial<TestBase> {}

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
  organization?: Organization;
  priorityLevel?: PriorityLevel;
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
  prompt: TestPromptCreate;
  behavior: string;
  category: string;
  topic: string;
  test_configuration?: Record<string, any>;
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
  test_configuration?: Record<string, any>;
  prompt?: Record<string, any>;
}
