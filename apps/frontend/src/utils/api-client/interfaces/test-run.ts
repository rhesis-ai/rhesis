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

export interface VerdictKpis {
  pass_rate: number | null;
  tests_executed: number;
  tests_total: number;
  verdicts_resolved: number;
  verdicts_planned: number;
  failures: number;
}

export interface VerdictRequirement {
  id: string | null;
  name: string;
  metric_keys: string[];
}

export interface VerdictRow {
  requirement_id: string | null;
  metric_key: string;
  metric_name: string;
  metric_id: string | null;
  ambiguous: boolean;
  verdicts: string;
  overrides: string;
  passed: number;
  failed: number;
  pending: number;
}

export interface VerdictMatrix {
  test_run_id: string;
  project_id: string | null;
  status: string;
  is_terminal: boolean;
  version: number;
  test_ids: string[] | null;
  test_status: string;
  requirements: VerdictRequirement[];
  rows: VerdictRow[];
  kpis: VerdictKpis;
}
