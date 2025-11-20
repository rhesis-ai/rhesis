import {
  getTestResultStatus,
  getTestResultStatusWithReview,
  getTestResultLabel,
  getTestResultLabelWithReview,
  hasConflictingReview,
  hasExecutionError,
} from '../testResultStatus';
import {
  TestResultDetail,
  MetricResult,
} from '../api-client/interfaces/test-results';

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

// Helper to create valid review
const createReview = (statusName: string, comments: string = 'Test') => ({
  review_id: '12345678-1234-1234-1234-123456789012' as const,
  status: {
    status_id: '12345678-1234-1234-1234-123456789012' as const,
    name: statusName,
  },
  user: {
    user_id: '12345678-1234-1234-1234-123456789012' as const,
    name: 'Test User',
  },
  comments,
  updated_at: '2025-01-01T00:00:00Z',
  created_at: '2025-01-01T00:00:00Z',
  target: { type: 'test' as const, reference: null },
});

describe('testResultStatus', () => {
  describe('getTestResultStatus', () => {
    it('should return Pass when all metrics are successful', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
            metric2: createMetricResult(true, 0.85, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(getTestResultStatus(test as TestResultDetail)).toBe('Pass');
    });

    it('should return Fail when some metrics fail', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
            metric2: createMetricResult(false, 0.5, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(getTestResultStatus(test as TestResultDetail)).toBe('Fail');
    });

    it('should return Error when no metrics are present', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {},
          execution_time: 1.5,
        },
      };
      expect(getTestResultStatus(test as TestResultDetail)).toBe('Error');
    });

    it('should return Error when test_metrics is undefined', () => {
      const test: Partial<TestResultDetail> = {};
      expect(getTestResultStatus(test as TestResultDetail)).toBe('Error');
    });
  });

  describe('getTestResultStatusWithReview', () => {
    it('should prioritize human review over automated metrics when review exists', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(false, 0.5, 0.8),
          },
          execution_time: 1.5,
        },
        last_review: createReview('Passed', 'Looks good'),
      };
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Pass'
      );
    });

    it('should return Fail when review status indicates failure', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
          },
          execution_time: 1.5,
        },
        last_review: createReview('Failed', 'Needs work'),
      };
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Fail'
      );
    });

    it('should handle review status with "success" in name', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(false, 0.5, 0.8),
          },
          execution_time: 1.5,
        },
        last_review: createReview('Success', 'Good'),
      };
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Pass'
      );
    });

    it('should handle review status with "completed" in name', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(false, 0.5, 0.8),
          },
          execution_time: 1.5,
        },
        last_review: createReview('Completed', 'Done'),
      };
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Pass'
      );
    });

    it('should return Error when review exists but no metrics or goal evaluation', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: { metrics: {}, execution_time: 1.5 },
        last_review: createReview('Passed', 'Good'),
      };
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Error'
      );
    });

    it('should accept review when goal_evaluation exists (multi-turn)', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: { metrics: {}, execution_time: 1.5 },
        test_output: {
          output: 'Test output',
          context: [],
          session_id: '12345678-1234-1234-1234-123456789012' as const,
          goal_evaluation: {
            all_criteria_met: false,
            reason: 'Some criteria failed',
            criteria_evaluations: [],
            confidence: 0.9,
            evidence: ['Test evidence'],
          },
        },
        last_review: createReview('Passed', 'Override'),
      };
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Pass'
      );
    });

    it('should fall back to automated metrics when no review exists', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Pass'
      );
    });

    it('should handle missing status.name property gracefully', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
          },
          execution_time: 1.5,
        },
        last_review: {
          review_id: '12345678-1234-1234-1234-123456789012' as const,
          status: {} as any,
          user: {
            user_id: '12345678-1234-1234-1234-123456789012' as const,
            name: 'Test User',
          },
          comments: 'Test',
          updated_at: '2025-01-01T00:00:00Z',
          created_at: '2025-01-01T00:00:00Z',
          target: { type: 'test', reference: null },
        },
      };
      // Should fall back to automated when status.name is missing
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Pass'
      );
    });
  });

  describe('getTestResultLabel', () => {
    it('should return "Passed" for passing test', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(getTestResultLabel(test as TestResultDetail)).toBe('Passed');
    });

    it('should return "Failed" for failing test', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(false, 0.5, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(getTestResultLabel(test as TestResultDetail)).toBe('Failed');
    });

    it('should return "Error" for test with no metrics', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: { metrics: {}, execution_time: 1.5 },
      };
      expect(getTestResultLabel(test as TestResultDetail)).toBe('Error');
    });
  });

  describe('getTestResultLabelWithReview', () => {
    it('should return review-based label when review exists', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(false, 0.5, 0.8),
          },
          execution_time: 1.5,
        },
        last_review: createReview('Passed', 'Override'),
      };
      expect(getTestResultLabelWithReview(test as TestResultDetail)).toBe(
        'Passed'
      );
    });

    it('should fall back to automated label when no review exists', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(getTestResultLabelWithReview(test as TestResultDetail)).toBe(
        'Passed'
      );
    });
  });

  describe('hasConflictingReview', () => {
    it('should return true when review exists and matches_review is false', () => {
      const test: Partial<TestResultDetail> = {
        last_review: createReview('Passed', 'Override'),
        matches_review: false,
      };
      expect(hasConflictingReview(test as TestResultDetail)).toBe(true);
    });

    it('should return false when review exists and matches_review is true', () => {
      const test: Partial<TestResultDetail> = {
        last_review: createReview('Passed', 'Agrees'),
        matches_review: true,
      };
      expect(hasConflictingReview(test as TestResultDetail)).toBe(false);
    });

    it('should return false when no review exists', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(hasConflictingReview(test as TestResultDetail)).toBe(false);
    });

    it('should return false when matches_review is undefined', () => {
      const test: Partial<TestResultDetail> = {
        last_review: createReview('Passed', 'Test'),
        matches_review: undefined,
      };
      expect(hasConflictingReview(test as TestResultDetail)).toBe(false);
    });
  });

  describe('hasExecutionError', () => {
    it('should return true when no metrics are present', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: { metrics: {}, execution_time: 1.5 },
      };
      expect(hasExecutionError(test as TestResultDetail)).toBe(true);
    });

    it('should return true when test_metrics is undefined', () => {
      const test: Partial<TestResultDetail> = {};
      expect(hasExecutionError(test as TestResultDetail)).toBe(true);
    });

    it('should return false when metrics exist', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(hasExecutionError(test as TestResultDetail)).toBe(false);
    });
  });

  describe('edge cases', () => {
    it('should handle test with single metric', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(getTestResultStatus(test as TestResultDetail)).toBe('Pass');
    });

    it('should handle test with multiple metrics where one fails', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(true, 0.9, 0.8),
            metric2: createMetricResult(true, 0.85, 0.8),
            metric3: createMetricResult(false, 0.7, 0.8),
          },
          execution_time: 1.5,
        },
      };
      expect(getTestResultStatus(test as TestResultDetail)).toBe('Fail');
    });

    it('should handle case-insensitive status matching', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(false, 0.5, 0.8),
          },
          execution_time: 1.5,
        },
        last_review: createReview('PASSED', 'Override'),
      };
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Pass'
      );
    });

    it('should handle review status with "pass" substring', () => {
      const test: Partial<TestResultDetail> = {
        test_metrics: {
          metrics: {
            metric1: createMetricResult(false, 0.5, 0.8),
          },
          execution_time: 1.5,
        },
        last_review: createReview('pass-review', 'Override'),
      };
      expect(getTestResultStatusWithReview(test as TestResultDetail)).toBe(
        'Pass'
      );
    });
  });
});
