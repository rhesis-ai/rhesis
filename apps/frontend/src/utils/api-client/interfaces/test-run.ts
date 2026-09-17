import { UUID } from 'crypto';
import { UserReference, Status } from './tests';
import { TestConfigurationDetail } from './test-configuration';
import { Tag } from './tag';
import type { WithPermittedActions } from '@/types/affordances';
import type { VersionInfoSource } from '@/constants/version-info';

/**
 * Run attributes the UI reads by name. The index signature keeps this assignable wherever a
 * plain Record was used before, while letting consumers narrow without casting.
 */
export interface TestRunAttributes {
  version_info?: Record<string, unknown>;
  version_info_source?: VersionInfoSource;
  [key: string]: unknown;
}

// Base interfaces for TestRun
export interface TestRunBase {
  name?: string;
  attributes?: TestRunAttributes;
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
  usage?: TestRunUsage;
}

/**
 * Token and cost totals aggregated from a run's traces, and the models behind them.
 *
 * The numbers are always present on a list row; `models` being empty is what separates
 * "this run traced nothing" from "it traced something that cost nothing", so the grid
 * keys its dash off that rather than off a zero.
 */
export interface TestRunUsage {
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  total_input_cost_usd: number;
  total_output_cost_usd: number;
  models: string[];
  providers: string[];
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
  annotations_count: number;
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
  /**
   * Execution phase offsets in deciseconds from the run's timing origin,
   * aligned to test_ids' order. null where a phase wasn't reached or wasn't
   * recorded; the whole array is null when no timing exists (an old run whose
   * cache lapsed, or one too large to be worth animating), in which case the
   * grid renders settled.
   */
  test_started_ds: (number | null)[] | null;
  test_generated_ds: (number | null)[] | null;
  test_resolved_ds: (number | null)[] | null;
  /** How far into the run the server is, same units and origin. */
  elapsed_ds: number | null;
  requirements: VerdictRequirement[];
  rows: VerdictRow[];
  kpis: VerdictKpis;
}
