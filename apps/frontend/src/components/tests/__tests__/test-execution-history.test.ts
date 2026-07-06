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
      id: 'a1111111-1111-4111-8111-111111111111',
      test_run_id: 'b1111111-1111-4111-8111-111111111111',
      updated_at: '2026-07-01T10:00:00Z',
      test_configuration_id: 'c1111111-1111-4111-8111-111111111111',
      created_at: '2026-07-01T10:00:00Z',
      test_metrics: {
        metrics: {
          a: { is_successful: true },
          b: { is_successful: true },
        },
        execution_time: 1,
      },
    } as unknown as TestResultDetail;

    const row = mapTestResultToHistoryRow(
      result,
      new Map([['b1111111-1111-4111-8111-111111111111', 'spinning-caracal']])
    );

    expect(row.passed).toBe(true);
    expect(row.passedMetrics).toBe(2);
    expect(row.totalMetrics).toBe(2);
    expect(row.testRunName).toBe('spinning-caracal');
  });

  it('prefers expanded test_run name over lookup map', () => {
    const result = {
      id: 'a1111111-1111-4111-8111-111111111111',
      test_run_id: 'b1111111-1111-4111-8111-111111111111',
      test_run: {
        id: 'b1111111-1111-4111-8111-111111111111',
        name: 'embedded-run-name',
      },
      updated_at: '2026-07-01T10:00:00Z',
      test_configuration_id: 'c1111111-1111-4111-8111-111111111111',
      created_at: '2026-07-01T10:00:00Z',
      test_metrics: { metrics: {}, execution_time: 0 },
    } as unknown as TestResultDetail;

    const row = mapTestResultToHistoryRow(
      result,
      new Map([['b1111111-1111-4111-8111-111111111111', 'map-name']])
    );

    expect(row.testRunName).toBe('embedded-run-name');
  });

  it('computes fail when any metric fails', () => {
    const result = {
      id: 'd2222222-2222-4222-8222-222222222222',
      test_run_id: 'e2222222-2222-4222-8222-222222222222',
      updated_at: '2026-07-02T10:00:00Z',
      test_configuration_id: 'c1111111-1111-4111-8111-111111111111',
      created_at: '2026-07-02T10:00:00Z',
      test_metrics: {
        metrics: {
          a: { is_successful: true },
          b: { is_successful: false },
        },
        execution_time: 1,
      },
    } as unknown as TestResultDetail;

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
