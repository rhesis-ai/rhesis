import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import { getEffectiveTestResultStatus } from '@/utils/test-result-status';
import type { TestResultStatus } from '@/constants/outcomes';

import type { ApiClientFactory } from '@/utils/api-client/client-factory';

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

const MAX_RESULTS = 100;

/**
 * The test's most recent results, one row per test run. Runs the results
 * endpoint doesn't embed a name for are looked up individually so every row
 * has one. Shared by the server prefetch and the client hook.
 */
export async function fetchTestExecutionHistory(
  factory: ApiClientFactory,
  testId: string
): Promise<TestExecutionHistoryRow[]> {
  const results = await factory.getTestResultsClient().getTestResults({
    filter: `test_id eq '${testId}'`,
    limit: MAX_RESULTS,
    skip: 0,
    sort_by: 'created_at',
    sort_order: 'desc',
  });

  const testRunNames = new Map<string, string>();
  for (const result of results.data) {
    if (result.test_run_id && result.test_run?.name) {
      testRunNames.set(result.test_run_id, result.test_run.name);
    }
  }

  const missingTestRunIds = [
    ...new Set(
      results.data
        .filter(
          (r): r is typeof r & { test_run_id: string } =>
            !!r.test_run_id && !testRunNames.has(r.test_run_id)
        )
        .map(r => r.test_run_id)
    ),
  ];

  if (missingTestRunIds.length > 0) {
    const testRunsClient = factory.getTestRunsClient();
    const testRuns = await Promise.allSettled(
      missingTestRunIds.map(id => testRunsClient.getTestRun(id))
    );
    testRuns.forEach((result, index) => {
      const id = missingTestRunIds[index];
      testRunNames.set(
        id,
        result.status === 'fulfilled' ? result.value.name || id : id
      );
    });
  }

  return dedupeHistoryByTestRun(
    results.data.map(result => mapTestResultToHistoryRow(result, testRunNames))
  );
}
