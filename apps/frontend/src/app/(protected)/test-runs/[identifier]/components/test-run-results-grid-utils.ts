import {
  TestResultDetail,
  MetricResult,
} from '@/utils/api-client/interfaces/test-results';
import {
  getTestEvaluationSummary,
  isPassedStatusName,
} from '@/utils/test-result-status';

export type TestResultDisplayStatus = {
  passed: boolean;
  label: string;
  count: string;
  isOverruled: boolean;
  hasConflict: boolean;
  automatedPassed?: boolean;
  hasExecutionError: boolean;
  reviewData?: {
    reviewer: string;
    comments: string;
    updated_at?: string;
    newStatus: string;
  };
};

function truncateText(text: string, maxLength: number) {
  if (text.length <= maxLength) return text;
  return `${text.substring(0, maxLength)}...`;
}

export function getGoalContent(
  test: TestResultDetail,
  prompts: Record<string, { content: string; name?: string }>,
  isMultiTurn: boolean
): string {
  if (isMultiTurn) {
    return test.test_output?.test_configuration?.goal || 'N/A';
  }
  if (test.prompt_id && prompts[test.prompt_id]) {
    return prompts[test.prompt_id].content;
  }
  return test.test?.prompt?.content || 'N/A';
}

export function getEvaluationContent(test: TestResultDetail): string {
  return getTestEvaluationSummary(test) || '—';
}

export function getFailedMetricNames(test: TestResultDetail): string[] {
  const metrics = test.test_metrics?.metrics || {};
  return Object.entries(metrics)
    .filter(([_, metric]) => !metric.is_successful)
    .map(([name]) => name);
}

export function getTestResultDisplayStatus(
  test: TestResultDetail,
  isMultiTurn: boolean
): TestResultDisplayStatus {
  if (isMultiTurn && test.test_output?.goal_evaluation) {
    const allMetrics = test.test_metrics?.metrics || {};
    const allMetricValues = Object.values(allMetrics);
    const hasTestMetrics = allMetricValues.length > 0;

    const allCriteriaMet = hasTestMetrics
      ? allMetricValues.every((m: MetricResult) => m.is_successful)
      : test.test_output.goal_evaluation.all_criteria_met;

    const totalCriteria = hasTestMetrics
      ? allMetricValues.length
      : test.test_output.goal_evaluation.criteria_evaluations?.length || 0;
    const metCriteria = hasTestMetrics
      ? allMetricValues.filter((m: MetricResult) => m.is_successful).length
      : test.test_output.goal_evaluation.criteria_evaluations?.filter(
          c => c.met
        )?.length || 0;

    const originalPassed = allCriteriaMet === true;
    const lastReview = test.last_review;

    if (lastReview && lastReview.status?.name) {
      const reviewPassed = isPassedStatusName(lastReview.status.name);
      const hasConflict = reviewPassed !== originalPassed;

      return {
        passed: reviewPassed,
        label: reviewPassed ? 'Passed' : 'Failed',
        count: `${metCriteria}/${totalCriteria}`,
        isOverruled: true,
        hasConflict,
        automatedPassed: originalPassed,
        hasExecutionError: false,
        reviewData: {
          reviewer: lastReview.user?.name || 'Unknown',
          comments: lastReview.comments,
          updated_at: lastReview.updated_at,
          newStatus: reviewPassed ? 'passed' : 'failed',
        },
      };
    }

    const hasExecutionError = test.test_output.status === 'error';
    const hasExecutionFailure = test.test_output.status === 'failure';

    if (hasExecutionError) {
      return {
        passed: false,
        label: 'Error',
        count: `${metCriteria}/${totalCriteria}`,
        isOverruled: false,
        hasConflict: false,
        hasExecutionError: true,
      };
    }

    if (hasExecutionFailure) {
      return {
        passed: false,
        label: 'Failed',
        count: `${metCriteria}/${totalCriteria}`,
        isOverruled: false,
        hasConflict: false,
        hasExecutionError: false,
      };
    }

    return {
      passed: originalPassed,
      label: originalPassed ? 'Passed' : 'Failed',
      count: `${metCriteria}/${totalCriteria}`,
      isOverruled: false,
      hasConflict: false,
      automatedPassed: originalPassed,
      hasExecutionError: false,
    };
  }

  const metrics = test.test_metrics?.metrics || {};
  const metricValues = Object.values(metrics);
  const totalMetrics = metricValues.length;
  const passedMetrics = metricValues.filter(m => m.is_successful).length;
  const hasExecutionError = !test.test_metrics || totalMetrics === 0;

  if (hasExecutionError) {
    return {
      passed: false,
      label: 'Error',
      count: '0/0',
      isOverruled: false,
      hasConflict: false,
      hasExecutionError: true,
    };
  }

  const originalPassed = passedMetrics === totalMetrics;
  const lastReview = test.last_review;

  if (lastReview && lastReview.status?.name) {
    const reviewPassed = isPassedStatusName(lastReview.status.name);
    const hasConflict = reviewPassed !== originalPassed;

    return {
      passed: reviewPassed,
      label: reviewPassed ? 'Passed' : 'Failed',
      count: `${passedMetrics}/${totalMetrics}`,
      isOverruled: true,
      hasConflict,
      automatedPassed: originalPassed,
      hasExecutionError: false,
      reviewData: {
        reviewer: lastReview.user?.name || 'Unknown',
        comments: lastReview.comments,
        updated_at: lastReview.updated_at,
        newStatus: reviewPassed ? 'passed' : 'failed',
      },
    };
  }

  return {
    passed: originalPassed,
    label: originalPassed ? 'Passed' : 'Failed',
    count: `${passedMetrics}/${totalMetrics}`,
    isOverruled: false,
    hasConflict: false,
    automatedPassed: originalPassed,
    hasExecutionError: false,
  };
}

export { truncateText };
