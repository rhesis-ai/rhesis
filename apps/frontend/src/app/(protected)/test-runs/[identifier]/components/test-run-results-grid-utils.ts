import {
  TestResultDetail,
  MetricResult,
} from '@/utils/api-client/interfaces/test-results';
import {
  getTestEvaluationSummary,
  getEffectiveTestResultStatus,
  getTestResultLabel,
  isPassedStatusName,
} from '@/utils/test-result-status';
import { getEndpointFailure } from '@/utils/endpoint-failure';
import { getLatestMetricAnnotationForResult } from './result-annotations';

export type TestResultDisplayStatus = {
  passed: boolean;
  label: string;
  count: string;
  isOverruled: boolean;
  hasConflict: boolean;
  automatedPassed?: boolean;
  hasExecutionError: boolean;
  errorReason?: string;
  annotationData?: {
    annotator: string;
    comments: string;
    updated_at?: string;
    newStatus: 'passed' | 'failed';
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
    const lastAnnotation = test.last_annotation;

    if (lastAnnotation && lastAnnotation.status?.name) {
      const annotationPassed = isPassedStatusName(lastAnnotation.status.name);
      const hasConflict = annotationPassed !== originalPassed;

      return {
        passed: getEffectiveTestResultStatus(test) === 'Pass',
        label: getTestResultLabel(test),
        count: `${metCriteria}/${totalCriteria}`,
        isOverruled: true,
        hasConflict,
        automatedPassed: originalPassed,
        hasExecutionError: false,
        annotationData: {
          annotator: lastAnnotation.user?.name || 'Unknown',
          comments: lastAnnotation.comments ?? '',
          updated_at: lastAnnotation.updated_at,
          newStatus: annotationPassed ? 'passed' : 'failed',
        },
      };
    }

    // test_output.status is a legacy per-run marker; it decides only whether
    // to show the execution-error affordance and its reason. The outcome
    // itself always comes from the backend, so this can no longer contradict
    // the chip shown elsewhere.
    const status = getEffectiveTestResultStatus(test);
    if (status === 'Error' || test.test_output.status === 'error') {
      return {
        passed: false,
        label: getTestResultLabel(test),
        count: `${metCriteria}/${totalCriteria}`,
        isOverruled: false,
        hasConflict: false,
        hasExecutionError: true,
        errorReason:
          test.test_output.goal_evaluation?.reason ||
          'Test execution encountered an error',
      };
    }

    // No entity-level annotation, but a metric-targeted one may still exist.
    const latestMetricAnnotation = getLatestMetricAnnotationForResult(test);
    if (latestMetricAnnotation?.status?.name) {
      const annotationPassed = isPassedStatusName(
        latestMetricAnnotation.status.name
      );

      return {
        passed: getEffectiveTestResultStatus(test) === 'Pass',
        label: getTestResultLabel(test),
        count: `${metCriteria}/${totalCriteria}`,
        isOverruled: true,
        hasConflict: false,
        automatedPassed: originalPassed,
        hasExecutionError: false,
        annotationData: {
          annotator: latestMetricAnnotation.user?.name || 'Unknown',
          comments: latestMetricAnnotation.comments ?? '',
          updated_at: latestMetricAnnotation.updated_at,
          newStatus: annotationPassed ? 'passed' : 'failed',
        },
      };
    }

    return {
      passed: getEffectiveTestResultStatus(test) === 'Pass',
      label: getTestResultLabel(test),
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
  // Pre-annotation values: `originalPassed` below is the automated baseline the
  // conflict indicator compares the human verdict against, so a metric an
  // annotation already flipped must not move it.
  const passedMetrics = metricValues.filter(
    m => m.override?.original_value ?? m.is_successful
  ).length;
  const hasExecutionError = !test.test_metrics || totalMetrics === 0;

  if (hasExecutionError) {
    return {
      passed: false,
      label: 'Error',
      count: '0/0',
      isOverruled: false,
      hasConflict: false,
      hasExecutionError: true,
      errorReason:
        'No metrics to evaluate. Ensure the requirement has metrics configured.',
    };
  }

  const originalPassed = passedMetrics === totalMetrics;
  const lastAnnotation = test.last_annotation;

  if (lastAnnotation && lastAnnotation.status?.name) {
    const annotationPassed = isPassedStatusName(lastAnnotation.status.name);
    const hasConflict = annotationPassed !== originalPassed;

    return {
      passed: getEffectiveTestResultStatus(test) === 'Pass',
      label: getTestResultLabel(test),
      count: `${passedMetrics}/${totalMetrics}`,
      isOverruled: true,
      hasConflict,
      automatedPassed: originalPassed,
      hasExecutionError: false,
      annotationData: {
        annotator: lastAnnotation.user?.name || 'Unknown',
        comments: lastAnnotation.comments ?? '',
        updated_at: lastAnnotation.updated_at,
        newStatus: annotationPassed ? 'passed' : 'failed',
      },
    };
  }

  // No entity-level annotation, but a metric-targeted one may still exist
  // (e.g. an @mention annotation left on a specific metric). last_annotation only
  // tracks entity-level annotations, so without this the "Annotation" column
  // would read as unannotated even though the test has been annotated.
  const latestMetricAnnotation = getLatestMetricAnnotationForResult(test);
  if (latestMetricAnnotation?.status?.name) {
    const annotationPassed = isPassedStatusName(
      latestMetricAnnotation.status.name
    );

    return {
      passed: getEffectiveTestResultStatus(test) === 'Pass',
      label: getTestResultLabel(test),
      count: `${passedMetrics}/${totalMetrics}`,
      isOverruled: true,
      hasConflict: false,
      automatedPassed: originalPassed,
      hasExecutionError: false,
      annotationData: {
        annotator: latestMetricAnnotation.user?.name || 'Unknown',
        comments: latestMetricAnnotation.comments ?? '',
        updated_at: latestMetricAnnotation.updated_at,
        newStatus: annotationPassed ? 'passed' : 'failed',
      },
    };
  }

  return {
    passed: getEffectiveTestResultStatus(test) === 'Pass',
    label: getTestResultLabel(test),
    count: `${passedMetrics}/${totalMetrics}`,
    isOverruled: false,
    hasConflict: false,
    automatedPassed: originalPassed,
    hasExecutionError: false,
  };
}

export function getExecutionErrorTooltip(
  test: TestResultDetail,
  status: TestResultDisplayStatus,
  requirements?: Array<{ id: string; metrics: Array<unknown> }>
): string {
  if (!status.hasExecutionError) return '';

  // Was a local reimplementation that only matched failures carrying an HTTP status and
  // only read the flat shape, so SDK/connector errors and every multi-turn failure fell
  // through to the generic message.
  const failure = getEndpointFailure(test.test_output);
  if (failure) return failure.summary;

  const requirement = test.test?.requirement;
  if (requirement && requirements) {
    const reqData = requirements.find(r => r.id === requirement.id);
    if (reqData && reqData.metrics.length === 0) {
      return `No metrics to evaluate because the requirement "${requirement.name}" has no metrics configured`;
    }
  }

  return status.errorReason || '';
}

export { truncateText };
