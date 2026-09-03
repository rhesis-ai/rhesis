import {
  aggregateMetricStats,
  requirementHasHumanCorrection,
  computeReviewSummary,
  findMetricKey,
  getEffectiveMetricSuccess,
  getLatestMetricReviewForResult,
  isMetricCorrected,
  metricHasHumanCorrection,
  metricNameMatches,
  metricShowsHumanCorrection,
  resultHasAnyHumanReview,
  testHasHumanCorrection,
} from '../test-run-summary-utils';
import type {
  Review,
  TestResultDetail,
} from '@/utils/api-client/interfaces/test-results';
import type { UUID } from 'crypto';

const u = (n: number): UUID =>
  `00000000-0000-0000-0000-${String(n).padStart(12, '0')}` as UUID;

let resultCounter = 0;
let reviewCounter = 0;

function makeReview(overrides: Partial<Review> = {}): Review {
  reviewCounter += 1;
  return {
    review_id: u(100 + reviewCounter),
    status: { name: 'Pass' },
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
  it('counts each metric by its own automated result, even when a whole-test review disagrees', () => {
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
        passed: 1,
        failed: 1,
        automatedPassed: 1,
        automatedFailed: 1,
        humanReviewCount: 0,
      })
    );
  });

  it('attributes a failure to only the metric that failed, not every metric on the same test', () => {
    const results = [
      makeResult({
        last_review: undefined,
        status: { id: u(40), name: 'Fail' },
        metrics: {
          'Answer Relevancy': { is_successful: true },
          Faithfulness: { is_successful: false },
          'Contextual Precision': { is_successful: true },
        },
      }),
    ];

    const stats = aggregateMetricStats(results);
    const byName = Object.fromEntries(stats.map(s => [s.name, s]));

    expect(byName['Answer Relevancy']).toEqual(
      expect.objectContaining({ passed: 1, failed: 0 })
    );
    expect(byName.Faithfulness).toEqual(
      expect.objectContaining({ passed: 0, failed: 1 })
    );
    expect(byName['Contextual Precision']).toEqual(
      expect.objectContaining({ passed: 1, failed: 0 })
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

    const goalAchievement = result.test_metrics?.metrics?.['Goal Achievement'];
    expect(goalAchievement).toBeDefined();

    expect(
      getEffectiveMetricSuccess(
        goalAchievement as {
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
        last_review: makeReview({ status: { name: 'Pass' } }),
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
          status: { name: 'Pass' },
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
          reviews: [
            makeReview({
              status: { name: 'Pass' },
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
            status: { name: 'Pass' },
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
            status: { name: 'Pass' },
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
          status: { name: 'Pass' },
        }),
        status: { id: u(28), name: 'Fail' },
        metrics: {
          'Bias Detection': { is_successful: false },
        },
        test_reviews: {
          reviews: [
            makeReview({
              status: { name: 'Pass' },
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
          reviews: [
            makeReview({
              status: { name: 'Pass' },
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
        test: {
          requirement: { name: 'Compliance' },
        } as TestResultDetail['test'],
        status: { id: u(30), name: 'Fail' },
        last_review: makeReview({
          status: { name: 'Pass' },
        }),
        metrics: {
          'Bias Detection': { is_successful: false },
          'LMRC Risk': { is_successful: true },
          'XSS Detection': { is_successful: true },
        },
        test_reviews: {
          reviews: [
            makeReview({
              status: { name: 'Pass' },
              comments: '@Bias Detection is incorrect.',
              updated_at: '2026-01-01T00:00:01Z',
              target: { type: 'metric', reference: 'Bias Detection' },
            }),
            makeReview({
              status: { name: 'Pass' },
              comments: 'passed overall.',
              updated_at: '2026-01-01T00:00:02Z',
              target: { type: 'test_result', reference: null },
            }),
          ],
        },
      }),
      makeResult({
        last_review: makeReview({
          status: { name: 'Fail' },
        }),
        status: { id: u(35), name: 'Fail' },
        metrics: {
          'Bias Detection': { is_successful: false },
        },
      }),
    ];

    expect(metricHasHumanCorrection('Bias Detection', results)).toBe(true);
    expect(requirementHasHumanCorrection('Compliance', results)).toBe(true);

    const summary = computeReviewSummary(results);
    expect(summary.headline).toBe('2 tests');
    expect(summary.subtitle).toContain('1 corrected (metric)');
    expect(summary.subtitle).toContain('1 corrected (test)');
  });

  it('detects corrections from insights human_review_count', () => {
    expect(metricShowsHumanCorrection('Bias Detection', [], 1)).toBe(true);
    expect(metricShowsHumanCorrection('Bias Detection', [], 0)).toBe(false);
  });
});

describe('requirementHasHumanCorrection', () => {
  it('returns true when a test review changed the outcome for that requirement', () => {
    const results = [
      makeResult({
        test: { requirement: { name: 'Safety' } } as TestResultDetail['test'],
        status: { id: u(36), name: 'Fail' },
        last_review: makeReview({
          status: { name: 'Pass' },
        }),
        metrics: {},
      }),
    ];

    expect(testHasHumanCorrection(results[0])).toBe(true);
    expect(requirementHasHumanCorrection('Safety', results)).toBe(true);
    expect(requirementHasHumanCorrection('Other', results)).toBe(false);
  });

  it('returns false when review confirms automated outcome', () => {
    const results = [
      makeResult({
        test: { requirement: { name: 'Safety' } } as TestResultDetail['test'],
        status: { id: u(38), name: 'Pass' },
        last_review: makeReview({
          status: { name: 'Pass' },
        }),
        metrics: { Accuracy: { is_successful: true } },
      }),
    ];

    expect(requirementHasHumanCorrection('Safety', results)).toBe(false);
  });

  it('measures a test-level review against the pre-review automated value, not a metric review already applied to it', () => {
    // Metric flipped false -> true by an earlier metric-level review, so the
    // live is_successful is true while the automated value is still false.
    // A test-level review saying Fail therefore AGREES with the automated
    // outcome and is not a correction. Reading the live value here instead
    // of override.original_value would score it as one.
    const results = [
      makeResult({
        test: { requirement: { name: 'Safety' } } as TestResultDetail['test'],
        last_review: makeReview({ status: { name: 'Fail' } }),
        metrics: {
          Accuracy: {
            is_successful: true,
            override: { original_value: false },
          },
        },
      }),
    ];

    expect(testHasHumanCorrection(results[0])).toBe(false);
    expect(requirementHasHumanCorrection('Safety', results)).toBe(false);
  });

  it('does not flag requirement when only a metric in that requirement was corrected', () => {
    const results = [
      makeResult({
        test: {
          requirement: { name: 'Compliance' },
        } as TestResultDetail['test'],
        last_review: undefined,
        metrics: {
          'Bias Detection': {
            is_successful: true,
            override: { original_value: false },
          },
        },
      }),
    ];

    expect(requirementHasHumanCorrection('Compliance', results)).toBe(false);
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
          reviews: [
            makeReview({
              status: { name: 'Pass' },
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
        reviews: [
          makeReview({
            status: { name: 'Pass' },
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
