import {
  dedupeHistoryByTestRun,
  mapTestResultToHistoryRow,
  TestExecutionHistoryRow,
} from '../test-execution-history';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

function makeRow(
  overrides: Partial<TestExecutionHistoryRow>
): TestExecutionHistoryRow {
  return {
    id: 'result-1',
    testRunId: 'run-1',
    testRunName: 'run-one',
    passed: true,
    passedMetrics: 2,
    totalMetrics: 2,
    executedAt: '2026-07-01T10:00:00Z',
    ...overrides,
  };
}

describe('mapTestResultToHistoryRow', () => {
  it('computes pass when all metrics succeed', () => {
    const result = {
      id: 'result-1',
      test_run_id: 'run-1',
      created_at: '2026-07-01T10:00:00Z',
      test_metrics: {
        metrics: {
          a: { is_successful: true },
          b: { is_successful: true },
        },
      },
    } as TestResultDetail;

    const row = mapTestResultToHistoryRow(
      result,
      new Map([['run-1', 'spinning-caracal']])
    );

    expect(row.passed).toBe(true);
    expect(row.passedMetrics).toBe(2);
    expect(row.totalMetrics).toBe(2);
    expect(row.testRunName).toBe('spinning-caracal');
  });

  it('computes fail when any metric fails', () => {
    const result = {
      id: 'result-2',
      test_run_id: 'run-2',
      created_at: '2026-07-02T10:00:00Z',
      test_metrics: {
        metrics: {
          a: { is_successful: true },
          b: { is_successful: false },
        },
      },
    } as TestResultDetail;

    const row = mapTestResultToHistoryRow(result, new Map());

    expect(row.passed).toBe(false);
    expect(row.passedMetrics).toBe(1);
    expect(row.totalMetrics).toBe(2);
  });
});

describe('dedupeHistoryByTestRun', () => {
  it('keeps the most recent result per test run', () => {
    const rows = [
      makeRow({
        id: 'older',
        testRunId: 'run-1',
        executedAt: '2026-07-01T10:00:00Z',
      }),
      makeRow({
        id: 'newer',
        testRunId: 'run-1',
        executedAt: '2026-07-06T10:00:00Z',
      }),
      makeRow({
        id: 'other-run',
        testRunId: 'run-2',
        executedAt: '2026-07-05T10:00:00Z',
      }),
    ];

    const deduped = dedupeHistoryByTestRun(rows);

    expect(deduped).toHaveLength(2);
    expect(deduped.map(row => row.id)).toEqual(['newer', 'other-run']);
  });
});
