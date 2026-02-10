import { UUID } from 'crypto';
import { UserReference, Status } from './tests';
import { TestConfigurationDetail } from './test-configuration';
import { Tag } from './tag';

// Define Organization interface based on API response
export interface OrganizationReference {
  id: string;
  name: string;
  description?: string;
  email?: string;
  user_id?: UUID;
}

// Base interfaces for TestRun
export interface TestRunBase {
  name?: string;
  user_id?: UUID;
  organization_id?: UUID;
  status_id?: UUID;
  attributes?: Record<string, any>;
  test_configuration_id?: UUID;
  owner_id?: UUID;
  assignee_id?: UUID;
  tags?: Tag[];
}

export type TestRunCreate = TestRunBase;

export type TestRunUpdate = Partial<TestRunBase>;

export interface TestRun extends TestRunBase {
  id: UUID;
  created_at: string;
  updated_at: string;
}

export interface TestRunDetail extends TestRun {
  name?: string;
  user?: UserReference;
  status?: Status;
  test_configuration?: TestConfigurationDetail;
  organization?: OrganizationReference;
  priority?: number;
  assignee?: UserReference;
  owner?: UserReference;
  counts?: {
    comments: number;
    tasks: number;
  };
}
