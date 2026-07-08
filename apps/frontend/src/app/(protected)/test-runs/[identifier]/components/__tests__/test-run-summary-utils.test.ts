import {
  aggregateMetricStats,
  behaviorHasHumanCorrection,
  computeReviewSummary,
  findMetricKey,
  getEffectiveMetricSuccess,
  isMetricCorrected,
  metricHasHumanCorrection,
  metricHasReviewCorrectionFromStats,
  metricNameMatches,
  metricShowsHumanCorrection,
  testHasHumanCorrection,
  getLatestMetricReviewForResult,
  resultHasAnyHumanReview,
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
        humanReviewCount: 0,
      })
    );
  });

  it('uses metric override for automated counts and human review', () => {
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
        automatedPassed: 0,
        automatedFailed: 1,
        humanReviewCount: 1,
      })
    );
  });
});

describe('computeReviewSummary', () => {
  it('returns empty state when no reviews exist', () => {
    const summary = computeReviewSummary([
      makeResult({ last_review: undefined, metrics: {} }),
    ]);
    expect(summary).toEqual(
      expect.objectContaining({
        headline: '0',
        subtitle: 'No reviews yet',
      })
    );
  });

  it('counts test and metric corrections separately in subtitle', () => {
    const results = [
      makeResult({
        last_review: {
          id: 'review-1',
          status: { id: 's1', name: 'Pass' },
        },
        metrics: {
          'Goal Achievement': { is_successful: false },
          Accuracy: {
            is_successful: true,
            override: { original_value: false },
          },
        },
      }),
    ];

    const summary = computeReviewSummary(results);
    expect(summary.headline).toBe('1 test');
    expect(summary.subtitle).toContain('1 corrected (test)');
    expect(summary.subtitle).toContain('1 corrected (metric)');
    expect(summary.subtitle).not.toContain('confirmed');
  });
});

describe('metricHasHumanCorrection', () => {
  it('returns false when overall status disagrees with metrics but no review exists', () => {
    const results = [
      makeResult({
        last_review: undefined,
        status: { id: 's1', name: 'Fail' },
        metrics: { 'LMRC Risk': { is_successful: true } },
      }),
    ];

    expect(metricHasHumanCorrection('LMRC Risk', results)).toBe(false);
  });

  it('returns true when a metric override changed the outcome', () => {
    const results = [
      makeResult({
        last_review: undefined,
        metrics: {
          'LMRC Risk': {
            is_successful: true,
            override: { original_value: false },
          },
        },
      }),
    ];

    expect(metricHasHumanCorrection('LMRC Risk', results)).toBe(true);
  });

  it('returns false when only a test-level review changed the overall outcome', () => {
    const results = [
      makeResult({
        status: { id: 's1', name: 'Fail' },
        last_review: {
          id: 'review-1',
          status: { id: 's2', name: 'Pass' },
        },
        metrics: {
          'Goal Achievement': { is_successful: false },
          Accuracy: { is_successful: true },
        },
      }),
    ];

    expect(metricHasHumanCorrection('Goal Achievement', results)).toBe(false);
    expect(metricHasHumanCorrection('Accuracy', results)).toBe(false);
  });

  it('matches metric names with slug normalization', () => {
    const results = [
      makeResult({
        metrics: {
          'Bias Detection': {
            is_successful: true,
            override: { original_value: false },
          },
        },
      }),
    ];

    expect(findMetricKey(results[0], 'bias-detection')).toBe('Bias Detection');
    expect(metricNameMatches('Bias Detection', 'bias-detection')).toBe(true);
    expect(metricHasHumanCorrection('bias-detection', results)).toBe(true);
  });

  it('returns true when a metric-targeted review changed the outcome', () => {
    const results = [
      makeResult({
        last_review: undefined,
        metrics: {
          'Bias Detection': { is_successful: false },
        },
        test_reviews: {
          metadata: { total_reviews: 1 },
          reviews: [
            {
              review_id: 'review-1',
              status: { status_id: 's2', name: 'Pass' },
              user: { user_id: 'u1', name: 'Reviewer' },
              comments: '@[Bias Detection](metric:bias-detection) is incorrect.',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              target: { type: 'metric', reference: 'Bias Detection' },
            },
          ],
        },
      }),
    ];

    expect(isMetricCorrected(results[0], 'Bias Detection')).toBe(true);
    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
  });

  it('detects metric reviews from review_summary when test_reviews is omitted', () => {
    const results = [
      makeResult({
        last_review: undefined,
        metrics: {
          'Bias Detection': { is_successful: false },
        },
        review_summary: {
          'metric:Bias Detection': {
            target_type: 'metric',
            reference: 'Bias Detection',
            status: { status_id: 's2', name: 'Pass' },
            user: { user_id: 'u1', name: 'Reviewer' },
            updated_at: '2026-01-01T00:00:00Z',
            review_id: 'review-1',
          },
        },
      } as TestResultDetail),
    ];

    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
    expect(
      metricShowsHumanCorrection('Bias Detection', results, undefined)
    ).toBe(true);
  });

  it('detects metric reviews from review_summary keys with slug references', () => {
    const results = [
      makeResult({
        last_review: undefined,
        metrics: {
          'Bias Detection': { is_successful: false },
        },
        review_summary: {
          'metric:bias-detection': {
            target_type: 'metric',
            reference: 'bias-detection',
            status: { status_id: 's2', name: 'Pass' },
            user: { user_id: 'u1', name: 'Reviewer' },
            updated_at: '2026-01-01T00:00:00Z',
            review_id: 'review-1',
          },
        },
      } as TestResultDetail),
    ];

    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
  });

  it('detects @metric mentions in comments even when review target is test_result', () => {
    const results = [
      makeResult({
        last_review: {
          id: 'review-1',
          status: { id: 's2', name: 'Pass' },
        },
        status: { id: 's1', name: 'Fail' },
        metrics: {
          'Bias Detection': { is_successful: false },
        },
        test_reviews: {
          metadata: { total_reviews: 1 },
          reviews: [
            {
              review_id: 'review-1',
              status: { status_id: 's2', name: 'Pass' },
              user: { user_id: 'u1', name: 'Reviewer' },
              comments:
                '@[Bias Detection](metric:bias-detection) should pass after manual review.',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              target: { type: 'test_result', reference: null },
            },
          ],
        },
      }),
    ];

    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
    const summary = computeReviewSummary(results);
    expect(summary.metricReviewCount).toBe(1);
    expect(summary.correctionCount).toBeGreaterThanOrEqual(1);
  });

  it('detects plain @Metric Name mentions without markup', () => {
    const results = [
      makeResult({
        last_review: undefined,
        metrics: {
          'Bias Detection': { is_successful: false },
        },
        test_reviews: {
          metadata: { total_reviews: 1 },
          reviews: [
            {
              review_id: 'review-1',
              status: { status_id: 's2', name: 'Pass' },
              user: { user_id: 'u1', name: 'Reviewer' },
              comments: '@Bias Detection is incorrect.',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              target: { type: 'test_result', reference: null },
            },
          ],
        },
      }),
    ];

    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
    expect(
      computeReviewSummary(results).subtitle
    ).toBe('1 corrected (metric)');
  });

  it('detects metric correction alongside a separate test-level review', () => {
    const results = [
      makeResult({
        test: { behavior: { name: 'Compliance' } } as TestResultDetail['test'],
        status: { id: 's1', name: 'Fail' },
        last_review: {
          id: 'review-2',
          status: { id: 's2', name: 'Pass' },
        },
        metrics: {
          'Bias Detection': { is_successful: false },
          'LMRC Risk': { is_successful: true },
          'XSS Detection': { is_successful: true },
        },
        test_reviews: {
          metadata: { total_reviews: 2 },
          reviews: [
            {
              review_id: 'review-1',
              status: { status_id: 's2', name: 'Pass' },
              user: { user_id: 'u1', name: 'Reviewer' },
              comments: '@Bias Detection is incorrect.',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:01Z',
              target: { type: 'metric', reference: 'Bias Detection' },
            },
            {
              review_id: 'review-2',
              status: { status_id: 's2', name: 'Pass' },
              user: { user_id: 'u1', name: 'Reviewer' },
              comments: 'passed overall.',
              created_at: '2026-01-01T00:00:02Z',
              updated_at: '2026-01-01T00:00:02Z',
              target: { type: 'test_result', reference: null },
            },
          ],
        },
      }),
      makeResult({
        id: 'result-2',
        last_review: {
          id: 'review-3',
          status: { id: 's1', name: 'Fail' },
        },
        status: { id: 's1', name: 'Fail' },
        metrics: {
          'Bias Detection': { is_successful: false },
        },
      }),
    ];

    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
    expect(behaviorHasHumanCorrection('Compliance', results)).toBe(true);

    const summary = computeReviewSummary(results);
    expect(summary.headline).toBe('2 tests');
    expect(summary.subtitle).toContain('1 corrected (metric)');
    expect(summary.subtitle).toContain('1 corrected (test)');
  });

  it('detects corrections from stats human_review_count', () => {
    const rates = {
      'Bias Detection': {
        total: 5,
        passed: 2,
        failed: 3,
        pass_rate: 40,
        human_review_count: 1,
      },
    };

    expect(metricHasReviewCorrectionFromStats(rates, 'Bias Detection')).toBe(
      true
    );
    expect(metricHasReviewCorrectionFromStats(rates, 'bias-detection')).toBe(
      true
    );
  });
});

describe('behaviorHasHumanCorrection', () => {
  it('returns true when a test review changed the outcome for that behavior', () => {
    const results = [
      makeResult({
        test: { behavior: { name: 'Safety' } } as TestResultDetail['test'],
        status: { id: 's1', name: 'Fail' },
        last_review: {
          id: 'review-1',
          status: { id: 's2', name: 'Pass' },
        },
        metrics: {},
      }),
    ];

    expect(testHasHumanCorrection(results[0])).toBe(true);
    expect(behaviorHasHumanCorrection('Safety', results)).toBe(true);
    expect(behaviorHasHumanCorrection('Other', results)).toBe(false);
  });

  it('returns false when review confirms automated outcome', () => {
    const results = [
      makeResult({
        test: { behavior: { name: 'Safety' } } as TestResultDetail['test'],
        status: { id: 's1', name: 'Pass' },
        last_review: {
          id: 'review-1',
          status: { id: 's1', name: 'Pass' },
        },
        metrics: { Accuracy: { is_successful: true } },
      }),
    ];

    expect(behaviorHasHumanCorrection('Safety', results)).toBe(false);
  });

  it('does not flag behavior when only a metric in that behavior was corrected', () => {
    const results = [
      makeResult({
        test: { behavior: { name: 'Compliance' } } as TestResultDetail['test'],
        last_review: undefined,
        metrics: {
          'Bias Detection': {
            is_successful: true,
            override: { original_value: false },
          },
        },
      }),
    ];

    expect(behaviorHasHumanCorrection('Compliance', results)).toBe(false);
    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
  });
});

describe('confirmed metric reviews', () => {
  it('counts confirmed metric review in summary subtitle', () => {
    const results = [
      makeResult({
        last_review: undefined,
        metrics: {
          'API Key Detection': { is_successful: true },
        },
        test_reviews: {
          metadata: { total_reviews: 1 },
          reviews: [
            {
              review_id: 'review-1',
              status: { status_id: 's1', name: 'Pass' },
              user: { user_id: 'u1', name: 'Reviewer' },
              comments: '@API Key Detection is correct',
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
              target: { type: 'metric', reference: 'API Key Detection' },
            },
          ],
        },
      }),
    ];

    const summary = computeReviewSummary(results);
    expect(summary.headline).toBe('1 test');
    expect(summary.subtitle).toBe('1 reviewed (metric)');
    expect(summary.metricReviewCount).toBe(1);
    expect(summary.metricCorrectionCount).toBe(0);
  });

  it('exposes latest metric review for metric-only results', () => {
    const result = makeResult({
      last_review: undefined,
      metrics: {
        'API Key Detection': { is_successful: true },
      },
      test_reviews: {
        metadata: { total_reviews: 1 },
        reviews: [
          {
            review_id: 'review-1',
            status: { status_id: 's1', name: 'Pass' },
            user: { user_id: 'u1', name: 'Reviewer' },
            comments: '@API Key Detection is correct',
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
            target: { type: 'metric', reference: 'API Key Detection' },
          },
        ],
      },
    });

    expect(getLatestMetricReviewForResult(result)?.status?.name).toBe('Pass');
    expect(resultHasAnyHumanReview(result)).toBe(true);
  });
});
