import {
  aggregateMetricStats,
  behaviorHasHumanCorrection,
  computeReviewSummary,
  findMetricKey,
  getEffectiveMetricSuccess,
  getLatestMetricReviewForResult,
  isMetricCorrected,
  metricHasHumanCorrection,
  metricHasReviewCorrectionFromStats,
  metricNameMatches,
  metricShowsHumanCorrection,
  resultHasAnyHumanReview,
  testHasHumanCorrection,
} from '../test-run-summary-utils';
import type {
  Review,
  TestResultDetail,
  TestReviews,
} from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

let resultCounter = 0;
let reviewCounter = 0;

function makeReviewMetadata(totalReviews: number): TestReviews['metadata'] {
  return {
    last_updated_at: '2026-01-01T00:00:00Z',
    last_updated_by: { user_id: u(9), name: 'Reviewer' },
    total_reviews: totalReviews,
    latest_status: { status_id: u(10), name: 'Pass' },
  };
}

function makeReview(overrides: Partial<Review> = {}): Review {
  reviewCounter += 1;
  return {
    review_id: u(100 + reviewCounter),
    status: { status_id: u(200 + reviewCounter), name: 'Pass' },
    user: { user_id: u(9), name: 'Reviewer' },
    comments: '',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    target: { type: 'test_result', reference: null },
    ...overrides,
  };
}

function makeResult(
  overrides: Partial<TestResultDetail> & {
    metrics?: Record<
      string,
      { is_successful: boolean; override?: { original_value: boolean } }
    >;
  } = {}
): TestResultDetail {
  resultCounter += 1;
  const { metrics = {}, ...rest } = overrides;
  return {
    id: u(resultCounter),
    test_configuration_id: u(11),
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    test_metrics: { metrics, execution_time: 1 },
    status: { id: u(2), name: 'Pass' },
    last_review: makeReview(),
    ...rest,
  } as unknown as TestResultDetail;
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
      status: { id: u(12), name: 'Fail' },
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
        last_review: makeReview({ status: { status_id: u(20), name: 'Pass' } }),
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
        status: { id: u(21), name: 'Fail' },
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
        status: { id: u(22), name: 'Fail' },
        last_review: makeReview({
          status: { status_id: u(23), name: 'Pass' },
        }),
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
          metadata: makeReviewMetadata(1),
          reviews: [
            makeReview({
              status: { status_id: u(24), name: 'Pass' },
              comments:
                '@[Bias Detection](metric:bias-detection) is incorrect.',
              target: { type: 'metric', reference: 'Bias Detection' },
            }),
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
            status: { status_id: u(25), name: 'Pass' },
            user: { user_id: u(9), name: 'Reviewer' },
            updated_at: '2026-01-01T00:00:00Z',
            review_id: u(101),
          },
        },
      }),
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
            status: { status_id: u(26), name: 'Pass' },
            user: { user_id: u(9), name: 'Reviewer' },
            updated_at: '2026-01-01T00:00:00Z',
            review_id: u(102),
          },
        },
      }),
    ];

    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
  });

  it('detects @metric mentions in comments even when review target is test_result', () => {
    const results = [
      makeResult({
        last_review: makeReview({
          status: { status_id: u(27), name: 'Pass' },
        }),
        status: { id: u(28), name: 'Fail' },
        metrics: {
          'Bias Detection': { is_successful: false },
        },
        test_reviews: {
          metadata: makeReviewMetadata(1),
          reviews: [
            makeReview({
              status: { status_id: u(27), name: 'Pass' },
              comments:
                '@[Bias Detection](metric:bias-detection) should pass after manual review.',
              target: { type: 'test_result', reference: null },
            }),
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
          metadata: makeReviewMetadata(1),
          reviews: [
            makeReview({
              status: { status_id: u(29), name: 'Pass' },
              comments: '@Bias Detection is incorrect.',
              target: { type: 'test_result', reference: null },
            }),
          ],
        },
      }),
    ];

    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
    expect(computeReviewSummary(results).subtitle).toBe('1 corrected (metric)');
  });

  it('detects metric correction alongside a separate test-level review', () => {
    const results = [
      makeResult({
        test: { behavior: { name: 'Compliance' } } as TestResultDetail['test'],
        status: { id: u(30), name: 'Fail' },
        last_review: makeReview({
          status: { status_id: u(31), name: 'Pass' },
        }),
        metrics: {
          'Bias Detection': { is_successful: false },
          'LMRC Risk': { is_successful: true },
          'XSS Detection': { is_successful: true },
        },
        test_reviews: {
          metadata: makeReviewMetadata(2),
          reviews: [
            makeReview({
              status: { status_id: u(32), name: 'Pass' },
              comments: '@Bias Detection is incorrect.',
              updated_at: '2026-01-01T00:00:01Z',
              target: { type: 'metric', reference: 'Bias Detection' },
            }),
            makeReview({
              status: { status_id: u(33), name: 'Pass' },
              comments: 'passed overall.',
              updated_at: '2026-01-01T00:00:02Z',
              target: { type: 'test_result', reference: null },
            }),
          ],
        },
      }),
      makeResult({
        last_review: makeReview({
          status: { status_id: u(34), name: 'Fail' },
        }),
        status: { id: u(35), name: 'Fail' },
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
        status: { id: u(36), name: 'Fail' },
        last_review: makeReview({
          status: { status_id: u(37), name: 'Pass' },
        }),
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
        status: { id: u(38), name: 'Pass' },
        last_review: makeReview({
          status: { status_id: u(39), name: 'Pass' },
        }),
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
          metadata: makeReviewMetadata(1),
          reviews: [
            makeReview({
              status: { status_id: u(40), name: 'Pass' },
              comments: '@API Key Detection is correct',
              target: { type: 'metric', reference: 'API Key Detection' },
            }),
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
        metadata: makeReviewMetadata(1),
        reviews: [
          makeReview({
            status: { status_id: u(41), name: 'Pass' },
            comments: '@API Key Detection is correct',
            target: { type: 'metric', reference: 'API Key Detection' },
          }),
        ],
      },
    });

    expect(getLatestMetricReviewForResult(result)?.status?.name).toBe('Pass');
    expect(resultHasAnyHumanReview(result)).toBe(true);
  });
});
