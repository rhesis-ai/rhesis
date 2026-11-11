import { ANNOTATION_TARGET_TYPES } from '../api-client/interfaces/annotation';
import {
  getEffectiveTestResultStatus,
  getTestResultLabel,
  hasConflictingAnnotation,
  isPassedStatusName,
  findStatusByCategory,
  getTestEvaluationDetails,
  getTestEvaluationSummary,
  matchesStatusFilter,
  TEST_RESULT_STATUS_NAMES,
} from '../test-result-status';
import {
  TestResultDetail,
  MetricResult,
} from '../api-client/interfaces/test-results';
import { Status } from '../api-client/interfaces/status';

// Helper to create valid metric result
const createMetricResult = (
  isSuccessful: boolean,
  score: number = 0.9,
  threshold: number = 0.8
): MetricResult => ({
  is_successful: isSuccessful,
  score,
  threshold,
  reason: 'Test reason',
  backend: 'test-backend',
  description: 'Test description',
});

/** One entity-level annotation as it arrives embedded on a result. */
const createAnnotation = (statusName: string, comments: string = 'Test') => ({
  annotation_id: '12345678-1234-1234-1234-123456789012',
  target_type: ANNOTATION_TARGET_TYPES.TEST_RESULT,
  reference: null,
  status: {
    status_id: '12345678-1234-1234-1234-123456789012' as const,
    name: statusName,
  },
  user: { name: 'Test User' },
  comments,
  updated_at: '2025-01-01T00:00:00Z',
});

describe('testResultStatus', () => {
  describe('matchesStatusFilter', () => {
    const result = (
      execution: TestResultDetail['execution'],
      verdict: TestResultDetail['verdict']
    ) => ({ execution, verdict }) as TestResultDetail;

    it('counts failed verdicts and errors as failed, like the Failures card', () => {
      expect(matchesStatusFilter(result('ok', 'fail'), 'failed')).toBe(true);
      expect(matchesStatusFilter(result('error', null), 'failed')).toBe(true);
      expect(matchesStatusFilter(result('ok', 'pass'), 'failed')).toBe(false);
    });

    it('puts an inconclusive result under Inconclusive only', () => {
      const inconclusive = result('ok', 'inconclusive');
      expect(matchesStatusFilter(inconclusive, 'inconclusive')).toBe(true);
      expect(matchesStatusFilter(inconclusive, 'failed')).toBe(false);
      expect(matchesStatusFilter(inconclusive, 'passed')).toBe(false);
      expect(matchesStatusFilter(result('ok', 'pass'), 'inconclusive')).toBe(
        false
      );
    });

    it('keeps only passes under Passed', () => {
      expect(matchesStatusFilter(result('ok', 'pass'), 'passed')).toBe(true);
      expect(matchesStatusFilter(result('error', null), 'passed')).toBe(false);
    });
  });

  describe('getEffectiveTestResultStatus', () => {
    it('returns Pass for execution=ok, verdict=pass', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'ok',
        verdict: 'pass',
      };
      expect(getEffectiveTestResultStatus(test as TestResultDetail)).toBe(
        'Pass'
      );
    });

    it('returns Fail for execution=ok, verdict=fail', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'ok',
        verdict: 'fail',
      };
      expect(getEffectiveTestResultStatus(test as TestResultDetail)).toBe(
        'Fail'
      );
    });

    it('returns Error for execution=error', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'error',
        verdict: null,
      };
      expect(getEffectiveTestResultStatus(test as TestResultDetail)).toBe(
        'Error'
      );
    });

    it('returns Inconclusive for an inconclusive verdict, not Error', () => {
      // A metric that scored but has no pass/fail threshold is its own
      // bucket -- the backend names it, and the verdict grid already renders
      // it distinctly. Collapsing it into Error made "Error" mean two things.
      const test: Partial<TestResultDetail> = {
        execution: 'ok',
        verdict: 'inconclusive',
      };
      expect(getEffectiveTestResultStatus(test as TestResultDetail)).toBe(
        'Inconclusive'
      );
    });

    it('labels an inconclusive result as Inconclusive', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'ok',
        verdict: 'inconclusive',
      };
      expect(getTestResultLabel(test as TestResultDetail)).toBe('Inconclusive');
    });

    it('returns Error for not_run/cancelled -- a persisted row never actually reaches these', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'not_run',
        verdict: null,
      };
      expect(getEffectiveTestResultStatus(test as TestResultDetail)).toBe(
        'Error'
      );
    });

    it('trusts execution/verdict even when it disagrees with raw metrics -- the backend already applied any review', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'ok',
        verdict: 'pass',
        test_metrics: {
          metrics: { metric1: createMetricResult(false) },
          execution_time: 1.5,
        },
        last_annotation: createAnnotation('Pass', 'Looks good'),
      };
      expect(getEffectiveTestResultStatus(test as TestResultDetail)).toBe(
        'Pass'
      );
    });
  });

  describe('getTestResultLabel', () => {
    it('returns "Passed" for a passing test', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'ok',
        verdict: 'pass',
      };
      expect(getTestResultLabel(test as TestResultDetail)).toBe('Passed');
    });

    it('returns "Failed" for a failing test', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'ok',
        verdict: 'fail',
      };
      expect(getTestResultLabel(test as TestResultDetail)).toBe('Failed');
    });

    it('returns "Error" for an execution error', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'error',
        verdict: null,
      };
      expect(getTestResultLabel(test as TestResultDetail)).toBe('Error');
    });
  });

  describe('hasConflictingAnnotation', () => {
    it('should return true when an annotation exists and matches_annotation is false', () => {
      const test: Partial<TestResultDetail> = {
        last_annotation: createAnnotation('Passed', 'Override'),
        matches_annotation: false,
      };
      expect(hasConflictingAnnotation(test as TestResultDetail)).toBe(true);
    });

    it('should return false when an annotation exists and matches_annotation is true', () => {
      const test: Partial<TestResultDetail> = {
        last_annotation: createAnnotation('Passed', 'Agrees'),
        matches_annotation: true,
      };
      expect(hasConflictingAnnotation(test as TestResultDetail)).toBe(false);
    });

    it('should return false when no review exists', () => {
      const test: Partial<TestResultDetail> = {
        execution: 'ok',
        verdict: 'pass',
      };
      expect(hasConflictingAnnotation(test as TestResultDetail)).toBe(false);
    });

    it('should return false when matches_annotation is undefined', () => {
      const test: Partial<TestResultDetail> = {
        last_annotation: createAnnotation('Passed', 'Test'),
        matches_annotation: undefined,
      };
      expect(hasConflictingAnnotation(test as TestResultDetail)).toBe(false);
    });
  });

  describe('isPassedStatusName', () => {
    it('returns true for the canonical Pass name', () => {
      expect(isPassedStatusName(TEST_RESULT_STATUS_NAMES.PASSED)).toBe(true);
    });

    it('returns false for the canonical Fail name', () => {
      expect(isPassedStatusName(TEST_RESULT_STATUS_NAMES.FAILED)).toBe(false);
    });

    it('is an exact match, not a substring guess -- a review status name is always canonical', () => {
      expect(isPassedStatusName('pass')).toBe(false);
      expect(isPassedStatusName('Successful')).toBe(false);
      expect(isPassedStatusName('Completed')).toBe(false);
    });
  });

  describe('findStatusByCategory', () => {
    const statuses: Status[] = [
      {
        id: '11111111-1111-1111-1111-111111111111',
        name: 'Pass',
        entity_type: 'TestResult',
      } as Status,
      {
        id: '22222222-2222-2222-2222-222222222222',
        name: 'Fail',
        entity_type: 'TestResult',
      } as Status,
    ];

    it('finds the canonical Pass status', () => {
      expect(findStatusByCategory(statuses, 'passed')?.name).toBe('Pass');
    });

    it('finds the canonical Fail status', () => {
      expect(findStatusByCategory(statuses, 'failed')?.name).toBe('Fail');
    });

    it('falls back to keyword matching when no canonical name exists', () => {
      const custom: Status[] = [
        {
          id: '33333333-3333-3333-3333-333333333333',
          name: 'Approved',
          entity_type: 'TestResult',
        } as Status,
      ];
      expect(findStatusByCategory(custom, 'passed')?.name).toBe('Approved');
    });

    it('returns undefined for an empty list', () => {
      expect(findStatusByCategory([], 'passed')).toBeUndefined();
    });
  });

  describe('getTestEvaluationSummary', () => {
    const withMetrics = (
      metrics: Record<string, MetricResult>,
      goalReason?: string
    ): TestResultDetail =>
      ({
        test_metrics: { metrics, execution_time: 1 },
        ...(goalReason && {
          test_output: {
            goal_evaluation: {
              all_criteria_met: true,
              confidence: 1,
              reason: goalReason,
              evidence: [],
              criteria_evaluations: [],
            },
          },
        }),
      }) as unknown as TestResultDetail;

    it('names the failing metric instead of a passing goal reason', () => {
      const test = withMetrics(
        {
          'Goal Achievement': {
            ...createMetricResult(true),
            reason: 'The system met all 3 criteria.',
          },
          'Honest Service Degradation': {
            ...createMetricResult(false),
            reason: 'The assistant never named the transit outage.',
          },
        },
        'The system met all 3 criteria.'
      );

      expect(getTestEvaluationSummary(test)).toBe(
        '1 of 2 metrics failed: Honest Service Degradation. The assistant never named the transit outage.'
      );
    });

    it('lists every failing metric and shows the first reason', () => {
      const test = withMetrics({
        relevance: { ...createMetricResult(false), reason: 'Off-topic.' },
        safety: { ...createMetricResult(false), reason: 'Unsafe advice.' },
        tone: createMetricResult(true),
      });

      expect(getTestEvaluationSummary(test)).toBe(
        '2 of 3 metrics failed: relevance, safety. Off-topic.'
      );
    });

    it('reports metrics that gave no verdict when none failed', () => {
      const test = withMetrics({
        relevance: {
          ...createMetricResult(true),
          is_successful: null,
          reason: 'Judge timed out.',
        },
        safety: createMetricResult(true),
      });

      expect(getTestEvaluationSummary(test)).toBe(
        '1 of 2 metrics gave no verdict: relevance. Judge timed out.'
      );
    });

    it('says all metrics passed', () => {
      expect(
        getTestEvaluationSummary(
          withMetrics({
            a: createMetricResult(true),
            b: createMetricResult(true),
          })
        )
      ).toBe('All 2 metrics passed.');
      expect(
        getTestEvaluationSummary(withMetrics({ a: createMetricResult(true) }))
      ).toBe('1 metric passed.');
    });

    it('ignores metrics that did not apply', () => {
      const test = withMetrics({
        a: createMetricResult(true),
        b: { ...createMetricResult(false), not_applicable: true },
      });

      expect(getTestEvaluationSummary(test)).toBe('1 metric passed.');
    });

    it('falls back to the goal reason when there are no metrics', () => {
      expect(
        getTestEvaluationSummary(
          withMetrics({}, 'Goal not met due to missing confirmation.')
        )
      ).toBe('Goal not met due to missing confirmation.');
    });
  });

  describe('getTestEvaluationDetails', () => {
    it('gives one line per metric with its verdict and reason', () => {
      const test = {
        test_metrics: {
          metrics: {
            relevance: { ...createMetricResult(false), reason: 'Off-topic.' },
            safety: { ...createMetricResult(true), reason: '' },
          },
          execution_time: 1,
        },
      } as unknown as TestResultDetail;

      expect(getTestEvaluationDetails(test)).toEqual([
        'relevance — Failed: Off-topic.',
        'safety — Passed',
      ]);
    });
  });
});
