import { UUID } from 'crypto';
import { UserReference, Status } from './tests';
import { TestConfigurationDetail } from './test-configuration';
import { Tag } from './tag';
import type { WithPermittedActions } from '@/types/affordances';

// Base interfaces for TestRun
export interface TestRunBase {
  name?: string;
  attributes?: Record<string, unknown>;
  test_configuration_id?: UUID;
  experiment_id?: UUID;
  tags?: Tag[];
}

export type TestRunCreate = TestRunBase;

export type TestRunUpdate = Partial<TestRunBase>;

export interface TestRun extends TestRunBase, WithPermittedActions {
  id: UUID;
  created_at: string;
  updated_at: string;
}

export interface TestRunDetail extends TestRun {
  name?: string;
  user?: UserReference;
  status?: Status;
  test_configuration?: TestConfigurationDetail;
  counts?: {
    comments: number;
    tasks: number;
    reviewed_tests?: number;
    corrected_tests?: number;
  };
  stats?: {
    total: number;
    passed: number;
  };
}

export interface TestRunBulkDeleteResponse {
  deleted_ids: string[];
  not_found_ids: string[];
  forbidden_ids: string[];
}
