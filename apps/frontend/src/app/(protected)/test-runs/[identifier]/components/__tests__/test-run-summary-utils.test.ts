import {
  aggregateMetricStats,
  getEffectiveMetricSuccess,
} from '../test-run-summary-utils';
import type { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

function makeResult(
  overrides: Partial<TestResultDetail> & {
    metrics?: Record<
      string,
      { is_successful: boolean; override?: { original_value: boolean } }
    >;
  }
): TestResultDetail {
  const { metrics = {}, ...rest } = overrides;
  return {
    id: 'result-1',
    test_metrics: { metrics, execution_time: 1 },
    status: { id: 's1', name: 'Pass' },
    last_review: {
      id: 'review-1',
      status: { id: 's1', name: 'Pass' },
    },
    ...rest,
  } as TestResultDetail;
}

describe('aggregateMetricStats', () => {
  it('counts effective passes when test-level review overrides failed metric', () => {
    const results = [
      makeResult({
        metrics: { 'Goal Achievement': { is_successful: false } },
      }),
      makeResult({
        metrics: { 'Goal Achievement': { is_successful: true } },
      }),
    ];

    const stats = aggregateMetricStats(results);
    const goal = stats.find(s => s.name === 'Goal Achievement');

    expect(goal).toEqual(
      expect.objectContaining({
        total: 2,
        passed: 2,
        failed: 0,
        automatedPassed: 1,
        automatedFailed: 1,
        humanReviewCount: 1,
      })
    );
  });

  it('uses metric override marker without counting test-level adjustment twice', () => {
    const result = makeResult({
      last_review: undefined,
      status: { id: '00000000-0000-0000-0000-000000000002', name: 'Fail' },
      metrics: {
        'Goal Achievement': {
          is_successful: true,
          override: { original_value: false },
        },
      },
    });

    expect(
      getEffectiveMetricSuccess(
        result,
        result.test_metrics!.metrics!['Goal Achievement'] as {
          is_successful: boolean;
          override?: { original_value: boolean };
        }
      )
    ).toBe(true);

    const stats = aggregateMetricStats([result]);
    expect(stats[0]).toEqual(
      expect.objectContaining({
        passed: 1,
        automatedPassed: 1,
        humanReviewCount: 0,
      })
    );
  });
});
