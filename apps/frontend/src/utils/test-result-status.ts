/**
 * Utility functions for determining test result status
 */

import { TestResultDetail } from './api-client/interfaces/test-results';
import { Status } from './api-client/interfaces/status';
import {
  displayStatusOf,
  STATUS_LABEL,
  type TestResultStatus,
} from '@/constants/outcomes';

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
 * Write-side only: resolves which Status row to attach when *submitting* a
 * review (see findStatusByCategory below). Never use this to classify an
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
 * or updating test result reviews. It first tries to find the canonical status
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
 *   await testResultsClient.createReview(testId, failedStatus.id, reason);
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
 * review by the time it reaches the client (the review write path applies
 * and persists the override synchronously; see
 * apps/backend/.../services/review_override.py).
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
 * Gets the label text for a test result status, accounting for any human
 * review (the backend's `execution`/`verdict` already do).
 *
 * @param test - The test result detail object
 * @returns The label text (e.g., "Passed", "Failed", "Error")
 */
export function getTestResultLabel(test: TestResultDetail): string {
  return STATUS_LABEL[getEffectiveTestResultStatus(test)];
}

/**
 * Whether a review's own recorded status name is a pass.
 *
 * A review's `status.name` is always canonical ("Pass"/"Fail") by
 * construction of the review-submission UI (every submission flow resolves
 * through `findStatusByCategory`'s canonical-name-first lookup) -- so this
 * is a direct read, not a guess. Read-side classification of an already-
 * recorded *result* should use `getEffectiveTestResultStatus` instead; this
 * is only for displaying what a specific review itself said.
 */
export function isPassedStatusName(statusName: string): boolean {
  return statusName === TEST_RESULT_STATUS_NAMES.PASSED;
}

/**
 * Checks if a test has a conflicting human review
 * (i.e., human review exists but doesn't match automated result)
 *
 * @param test - The test result detail object
 * @returns True if there's a conflicting review, false otherwise
 */
export function hasConflictingReview(test: TestResultDetail): boolean {
  return !!test.last_review && test.matches_review === false;
}

function isGoalMetricName(name: string): boolean {
  const lower = name.toLowerCase();
  return (
    lower.includes('goal') &&
    (lower.includes('achievement') || lower.includes('evaluation'))
  );
}

/**
 * Summary text for the Evaluation column in test run result tables.
 * Prefers goal evaluation / metric reasons over raw model output.
 */
export function getTestEvaluationSummary(test: TestResultDetail): string {
  const metrics = test.test_metrics?.metrics ?? {};
  const goalEvaluation = test.test_output?.goal_evaluation;

  const goalReason = goalEvaluation?.reason?.trim();
  if (goalReason) {
    return goalReason;
  }

  const goalMetric = Object.entries(metrics).find(([name]) =>
    isGoalMetricName(name)
  )?.[1];
  const goalMetricReason = goalMetric?.reason?.trim();
  if (goalMetricReason) {
    return goalMetricReason;
  }

  const criteriaReasons =
    goalEvaluation?.criteria_evaluations
      ?.map(criterion => criterion.reasoning?.trim())
      .filter(Boolean) ?? [];
  if (criteriaReasons.length > 0) {
    return criteriaReasons.join(' · ');
  }

  const failedMetricReasons = Object.values(metrics)
    .filter(metric => !metric.is_successful)
    .map(metric => metric.reason?.trim())
    .filter(Boolean);
  if (failedMetricReasons.length > 0) {
    return failedMetricReasons.join(' · ');
  }

  const metricReasons = Object.values(metrics)
    .map(metric => metric.reason?.trim())
    .filter(Boolean);
  if (metricReasons.length > 0) {
    return metricReasons.join(' · ');
  }

  const evidence = goalEvaluation?.evidence
    ?.map(item => item.trim())
    .filter(Boolean);
  if (evidence && evidence.length > 0) {
    return evidence.join(' · ');
  }

  return '';
}
