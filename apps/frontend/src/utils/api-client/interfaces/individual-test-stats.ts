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
    pass_rate: number;
    avg_execution_time_ms: number;
  };
  metric_breakdown: {
    [metricName: string]: {
      total: number;
      passed: number;
      failed: number;
      pass_rate: number;
    };
  };
  recent_runs: RecentTestRun[];
  metadata: {
    generated_at: string;
    test_id: string;
    organization_id: string;
    start_date: string | null;
    end_date: string | null;
    period: string;
    recent_runs_limit: number;
    available_metrics: string[];
  };
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
      score: number;
      reason: string | null;
    };
  };
}

export interface IndividualTestStatsOptions {
  recent_runs_limit?: number;
  months?: number;
  start_date?: string;
  end_date?: string;
}
