/**
 * Utility functions for determining test result status
 */

import type {
  MetricResult,
  TestResultDetail,
} from './api-client/interfaces/test-results';
import { Status } from './api-client/interfaces/status';
import {
  applicableMetrics,
  displayStatusOf,
  STATUS_LABEL,
  type TestResultStatus,
} from '@/constants/outcomes';
import { getEndpointFailure } from './endpoint-failure';

// Re-export the TestResultStatus type for convenience
export type { TestResultStatus } from '@/constants/outcomes';

/**
 * Canonical status names for TestResult entity type.
 * These match the exact status names in the backend database.
 */
export const TEST_RESULT_STATUS_NAMES = {
  PASSED: 'Pass',
  FAILED: 'Fail',
  ERROR: 'Error',
} as const;

/**
 * Keywords to match for each status category.
 * Used as a fallback when searching for statuses by semantic meaning.
 *
 * Note: These use substring matching (case-insensitive), so:
 * - 'pass' will match 'Pass', 'Passed', 'passing'
 * - 'success' will match 'Success', 'Successful'
 *
 * Write-side only: resolves which Status row to attach when *submitting* an
 * annotation (see findStatusByCategory below). Never use this to classify an
 * already-recorded result -- read `execution`/`verdict` (via
 * getEffectiveTestResultStatus) instead, which the backend has already
 * classified once, canonically.
 */
const STATUS_KEYWORDS = {
  // Passed: Test executed and all metrics passed
  passed: [
    'pass', // Matches: Pass, Passed, Passing
    'success', // Matches: Success, Successful
    'completed', // Matches: Completed, Complete
    'done', // Matches: Done
    'approved', // Matches: Approved
  ],

  // Failed: Test executed but some/all metrics failed
  failed: [
    'fail', // Matches: Fail, Fails, Failing
    'failed', // Explicit match for 'Failed'
    'failure', // Matches: Failure, Failures
    'unsuccessful', // Matches: Unsuccessful
    'rejected', // Matches: Rejected (for review context)
  ],

  // Error: Test execution error (no metrics to evaluate)
  error: [
    'error', // Matches: Error, Errors
    'abort', // Matches: Abort, Aborted (execution aborted)
    'cancel', // Matches: Cancel, Cancelled, Canceled (execution cancelled)
    'timeout', // Matches: Timeout, Timed out (execution timeout)
    'exception', // Matches: Exception (execution threw exception)
    'crash', // Matches: Crash, Crashed (execution crashed)
    'skip', // Matches: Skip, Skipped (test skipped/not evaluated)
  ],
} as const;

/**
 * Find a status by semantic category (passed/failed/error).
 *
 * This provides a centralized way to find the appropriate status when creating
 * or updating test result annotations. It first tries to find the canonical status
 * name, then falls back to keyword matching if needed.
 *
 * @param statuses - Array of available statuses for TestResult entity type
 * @param category - The semantic category: 'passed' or 'failed'
 * @returns The matching Status object, or undefined if not found
 *
 * @example
 * ```typescript
 * const statuses = await statusClient.getStatuses({ entity_type: 'TestResult' });
 * const failedStatus = findStatusByCategory(statuses, 'failed');
 * if (failedStatus) {
 *   await annotationsClient.createAnnotation({ ..., status_id: failedStatus.id });
 * }
 * ```
 */
export function findStatusByCategory(
  statuses: Status[],
  category: 'passed' | 'failed' | 'error'
): Status | undefined {
  if (!statuses || statuses.length === 0) {
    return undefined;
  }

  // First, try to find by canonical name (exact match)
  const canonicalName =
    category === 'passed'
      ? TEST_RESULT_STATUS_NAMES.PASSED
      : category === 'failed'
        ? TEST_RESULT_STATUS_NAMES.FAILED
        : TEST_RESULT_STATUS_NAMES.ERROR;

  const exactMatch = statuses.find(status => status.name === canonicalName);

  if (exactMatch) {
    return exactMatch;
  }

  // Fallback: search by keywords (case-insensitive)
  const keywords = STATUS_KEYWORDS[category];
  return statuses.find(status =>
    keywords.some(keyword => status.name.toLowerCase().includes(keyword))
  );
}

/**
 * Determines the effective test result status from the backend's
 * `execution`/`verdict` (see constants/outcomes.ts) -- the source of truth,
 * which already reflects any test-level, metric-level, or turn-level human
 * annotation by the time it reaches the client (the annotation write path
 * applies and persists the override synchronously; see
 * apps/backend/.../services/annotation_override/).
 *
 * @param test - The test result detail object
 * @returns The test status: 'Pass', 'Fail', or 'Error'
 */
export function getEffectiveTestResultStatus(
  test: TestResultDetail
): TestResultStatus {
  return displayStatusOf(test);
}

/**
 * Whether a result belongs under one of the Tests tab's status filters.
 *
 * "failed" is what the Failures card counts -- a failed verdict or an error.
 * Inconclusive is neither (no pass/fail verdict was given), so it has a
 * filter of its own.
 */
export function matchesStatusFilter(
  test: TestResultDetail,
  filter: 'passed' | 'failed' | 'inconclusive'
): boolean {
  const status = getEffectiveTestResultStatus(test);
  if (filter === 'passed') return status === 'Pass';
  if (filter === 'inconclusive') return status === 'Inconclusive';
  return status === 'Fail' || status === 'Error';
}

/**
 * Gets the label text for a test result status, accounting for any human
 * annotation (the backend's `execution`/`verdict` already do).
 *
 * @param test - The test result detail object
 * @returns The label text (e.g., "Passed", "Failed", "Error")
 */
export function getTestResultLabel(test: TestResultDetail): string {
  return STATUS_LABEL[getEffectiveTestResultStatus(test)];
}

/**
 * Whether an annotation's own recorded status name is a pass.
 *
 * An annotation's `status.name` is always canonical ("Pass"/"Fail") by
 * construction of the annotation drawer (every write resolves through
 * `findStatusByCategory`'s canonical-name-first lookup) -- so this is a direct
 * read, not a guess. Read-side classification of an already-recorded *result*
 * should use `getEffectiveTestResultStatus` instead; this is only for
 * displaying what a specific annotation itself said.
 */
export function isPassedStatusName(statusName: string): boolean {
  return statusName === TEST_RESULT_STATUS_NAMES.PASSED;
}

/**
 * Checks if a test has a conflicting human annotation
 * (i.e., a human annotation exists but doesn't match the automated result)
 *
 * @param test - The test result detail object
 * @returns True if there's a conflicting annotation, false otherwise
 */
export function hasConflictingAnnotation(test: TestResultDetail): boolean {
  return !!test.last_annotation && test.matches_annotation === false;
}

export function isGoalMetricName(name: string): boolean {
  const lower = name.toLowerCase();
  return (
    lower.includes('goal') &&
    (lower.includes('achievement') || lower.includes('evaluation'))
  );
}

function countMetrics(count: number): string {
  return `${count} metric${count === 1 ? '' : 's'}`;
}

function metricVerdictLabel(metric: MetricResult): string {
  if (metric.is_successful === true) return 'Passed';
  if (metric.is_successful === false) return 'Failed';
  return 'No verdict';
}

/**
 * Summary text for the Evaluation column in test run result tables.
 *
 * Describes the whole test: how many metrics failed (or gave no verdict), which ones,
 * and the first failing reason. It states facts about the metrics rather than the
 * test's verdict, so it stays true when a person overrules the result.
 */
export function getTestEvaluationSummary(test: TestResultDetail): string {
  const metrics = Object.entries(applicableMetrics(test.test_metrics?.metrics));

  if (metrics.length > 0) {
    const total = metrics.length;
    const failed = metrics.filter(([, m]) => m.is_successful === false);
    const noVerdict = metrics.filter(([, m]) => m.is_successful == null);
    const [headline, cause] =
      failed.length > 0
        ? [`${failed.length} of ${countMetrics(total)} failed`, failed]
        : noVerdict.length > 0
          ? [
              `${noVerdict.length} of ${countMetrics(total)} gave no verdict`,
              noVerdict,
            ]
          : [
              total === 1 ? '1 metric passed' : `All ${total} metrics passed`,
              [],
            ];

    if (cause.length === 0) return `${headline}.`;
    const names = cause.map(([name]) => name).join(', ');
    const reason = cause[0][1].reason?.trim();
    return reason
      ? `${headline}: ${names}. ${reason}`
      : `${headline}: ${names}.`;
  }

  const goalEvaluation = test.test_output?.goal_evaluation;
  const goalReason = goalEvaluation?.reason?.trim();
  if (goalReason) {
    return goalReason;
  }

  const evidence = goalEvaluation?.evidence
    ?.map(item => item.trim())
    .filter(Boolean);
  if (evidence && evidence.length > 0) {
    return evidence.join(' · ');
  }

  // Last resort, and the only thing available when the endpoint refused the call: there is
  // no metric reasoning to show because nothing was evaluated. Returning '' left the grid's
  // Evaluation cell showing a bare dash for the whole run.
  const failure = getEndpointFailure(test.test_output);
  if (failure) {
    return failure.summary;
  }

  return '';
}

/** One line per metric — "Name — Failed: reason" — for the Evaluation tooltip and search. */
export function getTestEvaluationDetails(test: TestResultDetail): string[] {
  return Object.entries(applicableMetrics(test.test_metrics?.metrics)).map(
    ([name, metric]) => {
      const reason = metric.reason?.trim();
      const verdict = metricVerdictLabel(metric);
      return reason
        ? `${name} — ${verdict}: ${reason}`
        : `${name} — ${verdict}`;
    }
  );
}
