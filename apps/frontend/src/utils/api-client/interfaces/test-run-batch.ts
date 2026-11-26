import type { ScheduleRunSettings } from './test-run-schedule';

/** Run several test sets, or every set carrying a tag, against one endpoint. */
export interface TestRunBatchCreate {
  test_set_ids?: string[];
  test_set_tag?: string;
  endpoint_id: string;
  /** Each test set runs once per entry; empty runs each set once. */
  experiments?: { experiment_id: string; version: string }[];
  run_settings?: ScheduleRunSettings & { reference_test_run_id?: string };
}

export interface TestRunBatchMember {
  test_set_id: string;
  test_set_name: string;
  experiment_id: string | null;
  version: string | null;
  test_configuration_id: string;
  test_run_id: string | null;
  test_run_name: string | null;
}

/** `batch_id` is null when the group is a single run. */
export interface TestRunBatch {
  batch_id: string | null;
  test_set_tag: string | null;
  members: TestRunBatchMember[];
}
