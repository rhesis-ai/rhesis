import { UUID } from 'crypto';
import { UserReference, TypeLookup, Topic, Status, Category } from './tests';
import { Prompt } from './prompt';
import { TestSet } from './test-set';
import { Endpoint } from './endpoint';

// Test Configuration interfaces
export interface TestConfigurationBase {
  endpoint_id: UUID;
  category_id?: UUID;
  topic_id?: UUID;
  prompt_id?: UUID;
  use_case_id?: UUID;
  test_set_id: UUID;
  user_id: UUID;
  organization_id?: UUID;
  status_id?: UUID;
  attributes?: Record<string, any>;
}

export type TestConfigurationCreate = TestConfigurationBase;

export type TestConfigurationUpdate = Partial<TestConfigurationBase>;

export interface TestConfiguration extends TestConfigurationBase {
  id: UUID;
  created_at: string;
  updated_at: string;
}

export interface UseCase {
  id: UUID;
  name: string;
  description?: string;
}

export interface TestConfigurationDetail extends TestConfiguration {
  endpoint?: Endpoint;
  category?: Category;
  topic?: Topic;
  prompt?: Prompt;
  use_case?: UseCase;
  test_set?: TestSet;
  user?: UserReference;
  status?: Status;
}

// Interface for the response of executing a test configuration
export interface TestConfigurationExecuteResponse {
  test_configuration_id: string;
  task_id: string;
  status: string;
  endpoint_id: string;
  test_set_id: string;
  user_id: string;
}
