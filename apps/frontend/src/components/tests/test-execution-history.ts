import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { getEffectiveTestResultStatus } from '@/utils/test-result-status';
import type { TestResultStatus } from '@/constants/outcomes';

export interface TestExecutionHistoryRow {
  id: string;
  testRunId: string;
  testRunName: string;
  /** The backend-computed outcome for this execution. */
  status: TestResultStatus;
  passed: boolean;
  passedMetrics: number;
  totalMetrics: number;
  executedAt: string;
}

export function mapTestResultToHistoryRow(
  result: TestResultDetail,
  testRunNamesMap: Map<string, string>
): TestExecutionHistoryRow {
  // Per-metric counts stay local -- they are display detail ("2/3 passed"),
  // not the execution's outcome. The outcome itself comes from the backend,
  // so a reviewed or errored run reads the same here as everywhere else.
  const metrics = result.test_metrics?.metrics || {};
  const metricValues = Object.values(metrics);
  const passedMetrics = metricValues.filter(m => m.is_successful).length;
  const totalMetrics = metricValues.length;
  const status = getEffectiveTestResultStatus(result);

  return {
    id: result.id,
    testRunId: result.test_run_id || 'unknown',
    testRunName: result.test_run_id
      ? result.test_run?.name ||
        testRunNamesMap.get(result.test_run_id) ||
        result.test_run_id
      : 'unknown',
    status,
    passed: status === 'Pass',
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
