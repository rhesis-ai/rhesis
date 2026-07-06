import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

export interface TestExecutionHistoryRow {
  id: string;
  testRunId: string;
  testRunName: string;
  passed: boolean;
  passedMetrics: number;
  totalMetrics: number;
  executedAt: string;
}

export function mapTestResultToHistoryRow(
  result: TestResultDetail,
  testRunNamesMap: Map<string, string>
): TestExecutionHistoryRow {
  const metrics = result.test_metrics?.metrics || {};
  const metricValues = Object.values(metrics);
  const passedMetrics = metricValues.filter(m => m.is_successful).length;
  const totalMetrics = metricValues.length;
  const passed = totalMetrics > 0 && passedMetrics === totalMetrics;

  return {
    id: result.id,
    testRunId: result.test_run_id || 'unknown',
    testRunName: result.test_run_id
      ? result.test_run?.name ||
        testRunNamesMap.get(result.test_run_id) ||
        result.test_run_id
      : 'unknown',
    passed,
    passedMetrics,
    totalMetrics,
    executedAt: result.created_at || new Date().toISOString(),
  };
}

export function dedupeHistoryByTestRun(
  rows: TestExecutionHistoryRow[]
): TestExecutionHistoryRow[] {
  const sorted = [...rows].sort(
    (a, b) =>
      new Date(b.executedAt).getTime() - new Date(a.executedAt).getTime()
  );

  const uniqueByTestRun = new Map<string, TestExecutionHistoryRow>();
  sorted.forEach(item => {
    if (!uniqueByTestRun.has(item.testRunId)) {
      uniqueByTestRun.set(item.testRunId, item);
    }
  });

  return Array.from(uniqueByTestRun.values()).sort(
    (a, b) =>
      new Date(b.executedAt).getTime() - new Date(a.executedAt).getTime()
  );
}
