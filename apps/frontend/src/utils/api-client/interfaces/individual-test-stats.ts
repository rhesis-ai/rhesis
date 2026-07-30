/**
 * Individual test statistics interface
 * Response from GET /tests/{test_id}/stats
 */

export interface IndividualTestStats {
  overall_summary: {
    total_test_runs: number;
    total_executions: number;
    passed: number;
    failed: number;
    avg_execution_time_ms: number;
  };
  recent_runs: RecentTestRun[];
}

export interface RecentTestRun {
  test_run_id: string;
  test_run_name: string;
  created_at: string;
  overall_passed: boolean;
  execution_time_ms: number;
  metrics: {
    [metricName: string]: {
      is_successful: boolean;
    };
  };
}

export interface IndividualTestStatsOptions {
  recent_runs_limit?: number;
  months?: number;
  start_date?: string;
  end_date?: string;
}
