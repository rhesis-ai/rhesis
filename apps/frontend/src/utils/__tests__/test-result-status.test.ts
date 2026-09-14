import { ANNOTATION_TARGET_TYPES } from '../api-client/interfaces/annotation';
import {
  getEffectiveTestResultStatus,
  getTestResultLabel,
  hasConflictingAnnotation,
  isPassedStatusName,
  findStatusByCategory,
  getTestEvaluationSummary,
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
    it('prefers goal_evaluation reason', () => {
      const test: Partial<TestResultDetail> = {
        test_output: {
          goal_evaluation: {
            all_criteria_met: false,
            confidence: 0.5,
            reason: 'Goal not met due to missing confirmation.',
            evidence: [],
            criteria_evaluations: [],
          },
        } as unknown as TestResultDetail['test_output'],
        test_metrics: {
          metrics: {
            'Goal Evaluation': createMetricResult(false),
          },
          execution_time: 1,
        },
      };

      expect(getTestEvaluationSummary(test as TestResultDetail)).toBe(
        'Goal not met due to missing confirmation.'
      );
    });

    it('falls back to goal metric reason when goal_evaluation reason is empty', () => {
      const test: Partial<TestResultDetail> = {
        test_output: {
          goal_evaluation: {
            all_criteria_met: false,
            confidence: 0.5,
            reason: '',
            evidence: [],
            criteria_evaluations: [],
          },
        } as unknown as TestResultDetail['test_output'],
        test_metrics: {
          metrics: {
            'Goal Achievement': {
              ...createMetricResult(false),
              reason: 'The assistant never confirmed the booking.',
            },
          },
          execution_time: 1,
        },
      };

      expect(getTestEvaluationSummary(test as TestResultDetail)).toBe(
        'The assistant never confirmed the booking.'
      );
    });

    it('uses failed metric reasons for single-turn tests', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            relevance: {
              ...createMetricResult(false),
              reason: 'Response was off-topic.',
            },
            safety: createMetricResult(true),
          },
          execution_time: 1,
        },
      };

      expect(getTestEvaluationSummary(test as TestResultDetail)).toBe(
        'Response was off-topic.'
      );
    });
  });
});
