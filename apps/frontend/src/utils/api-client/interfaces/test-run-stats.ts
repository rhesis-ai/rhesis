// Test Run Statistics Interfaces
// These interfaces match the backend response schemas

export interface StatusDistribution {
  status: string;
  count: number;
  percentage: number;
}

export interface ResultDistribution {
  total: number;
  passed: number;
  failed: number;
  pending: number;
  pass_rate: number;
}

export interface TestSetRunCount {
  test_set_name: string;
  run_count: number;
}

export interface ExecutorRunCount {
  executor_name: string;
  run_count: number;
}

export interface TestRunTimelineData {
  date: string;
  total_runs: number;
  status_breakdown: Record<string, number>;
  result_breakdown: Record<string, number>;
}

export interface TestRunOverallSummary {
  total_runs: number;
  unique_test_sets: number;
  unique_executors: number;
  most_common_status: string;
  pass_rate: number;
}

export interface TestRunStatsMetadata {
  generated_at: string;
  organization_id?: string;
  period: string;
  start_date: string;
  end_date: string;
  total_test_runs: number;
  mode: string;
  available_statuses: string[];
  available_test_sets: string[];
  available_executors: string[];
}

// Mode-specific response types
export interface TestRunStatsAll {
  status_distribution: StatusDistribution[];
  result_distribution: ResultDistribution;
  most_run_test_sets: TestSetRunCount[];
  top_executors: ExecutorRunCount[];
  timeline: TestRunTimelineData[];
  overall_summary: TestRunOverallSummary;
  metadata: TestRunStatsMetadata;
}

export interface TestRunStatsSummary {
  overall_summary: TestRunOverallSummary;
  metadata: TestRunStatsMetadata;
}

export interface TestRunStatsStatus {
  status_distribution: StatusDistribution[];
  metadata: TestRunStatsMetadata;
}

export interface TestRunStatsResults {
  result_distribution: ResultDistribution;
  metadata: TestRunStatsMetadata;
}

export interface TestRunStatsTests {
  most_run_test_sets: TestSetRunCount[];
  metadata: TestRunStatsMetadata;
}

export interface TestRunStatsExecutors {
  top_executors: ExecutorRunCount[];
  metadata: TestRunStatsMetadata;
}

export interface TestRunStatsTimeline {
  timeline: TestRunTimelineData[];
  metadata: TestRunStatsMetadata;
}

// Union type for all possible responses
export type TestRunStatsResponse =
  | TestRunStatsAll
  | TestRunStatsSummary
  | TestRunStatsStatus
  | TestRunStatsResults
  | TestRunStatsTests
  | TestRunStatsExecutors
  | TestRunStatsTimeline;

// Stats query parameters
export interface TestRunStatsParams {
  mode?:
    | 'all'
    | 'summary'
    | 'status'
    | 'results'
    | 'test_sets'
    | 'executors'
    | 'timeline';
  top?: number;
  months?: number;
  // Test run filters
  test_run_ids?: string[];
  // User-related filters
  user_ids?: string[];
  // Configuration filters
  endpoint_ids?: string[];
  test_set_ids?: string[];
  // Status filters
  status_list?: string[];
  // Date range filters
  start_date?: string;
  end_date?: string;
}
