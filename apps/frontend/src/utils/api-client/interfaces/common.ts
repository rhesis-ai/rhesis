// Test Results Stats specific modes based on API documentation
export type TestResultsStatsMode =
  | 'all'
  | 'summary'
  | 'metrics'
  | 'behavior'
  | 'category'
  | 'topic'
  | 'timeline'
  | 'test_runs'
  | 'ids'
  | 'behavior_detail';

// Comprehensive options for test results stats
export interface TestResultsStatsOptions {
  // Data mode selection
  mode?: TestResultsStatsMode;

  // Time range options
  months?: number;
  start_date?: string;
  end_date?: string;

  // Test-level filters
  test_set_ids?: string[];
  behavior_ids?: string[];
  category_ids?: string[];
  topic_ids?: string[];
  status_ids?: string[];
  test_ids?: string[];
  test_type_ids?: string[];

  // Test run filters
  test_run_id?: string; // Legacy single run support
  test_run_ids?: string[];

  // User-related filters
  user_ids?: string[];
  assignee_ids?: string[];
  owner_ids?: string[];

  // Other filters
  prompt_ids?: string[];
  priority_min?: number;
  priority_max?: number;
  tags?: string[];

  // mode='ids' filters
  metric_name?: string;
  outcome?: 'pass' | 'fail' | 'all';
  topic_name?: string;
}
