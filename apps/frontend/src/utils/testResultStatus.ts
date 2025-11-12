/**
 * Utility functions for determining test result status
 */

import { TestResultDetail } from './api-client/interfaces/test-results';
import { TestResultStatus } from '@/components/common/StatusChip';

// Re-export the TestResultStatus type for convenience
export type { TestResultStatus } from '@/components/common/StatusChip';

/**
 * Determines the test result status from a test result object
 * This function considers AUTOMATED metrics only. Use getTestResultStatusWithReview
 * to include human review overrides.
 *
 * @param test - The test result detail object
 * @returns The test status: 'Pass', 'Fail', or 'Error'
 */
export function getTestResultStatus(test: TestResultDetail): TestResultStatus {
  // Check if test has metrics
  const metrics = test.test_metrics?.metrics || {};
  const metricsCount = Object.keys(metrics).length;

  // If no metrics, it's an error (no way to evaluate the test)
  if (metricsCount === 0) {
    return 'Error';
  }

  // Count passed metrics
  const passedMetrics = Object.values(metrics).filter(
    metric => metric.is_successful
  ).length;

  // All metrics passed = Pass, otherwise Fail
  return passedMetrics === metricsCount ? 'Pass' : 'Fail';
}

/**
 * Determines the test result status, prioritizing human reviews over automated metrics
 *
 * @param test - The test result detail object
 * @returns The test status: 'Pass', 'Fail', or 'Error'
 */
export function getTestResultStatusWithReview(
  test: TestResultDetail
): TestResultStatus {
  // If there's a human review, prioritize it
  if (test.last_review && test.last_review.status?.name) {
    const reviewStatusName = String(test.last_review.status.name).toLowerCase();
    const reviewPassed =
      reviewStatusName.includes('pass') ||
      reviewStatusName.includes('success') ||
      reviewStatusName.includes('completed');

    // Check if test has valid metrics (either single-turn metrics or multi-turn goal_evaluation)
    const hasMetrics =
      test.test_metrics?.metrics &&
      Object.keys(test.test_metrics.metrics).length > 0;
    const hasGoalEvaluation = test.test_output?.goal_evaluation;

    // Return 'Error' only if there are no metrics AND no goal evaluation
    if (!hasMetrics && !hasGoalEvaluation) {
      return 'Error';
    }

    return reviewPassed ? 'Pass' : 'Fail';
  }

  // Fall back to automated metrics
  return getTestResultStatus(test);
}

/**
 * Gets the label text for a test result status
 * Uses automated result only. Use getTestResultLabelWithReview for human review consideration.
 *
 * @param test - The test result detail object
 * @returns The label text (e.g., "Passed", "Failed", "Error")
 */
export function getTestResultLabel(test: TestResultDetail): string {
  const status = getTestResultStatus(test);

  switch (status) {
    case 'Pass':
      return 'Passed';
    case 'Fail':
      return 'Failed';
    case 'Error':
      return 'Error';
    default:
      return 'Unknown';
  }
}

/**
 * Gets the label text for a test result status, prioritizing human reviews
 *
 * @param test - The test result detail object
 * @returns The label text (e.g., "Passed", "Failed", "Error")
 */
export function getTestResultLabelWithReview(test: TestResultDetail): string {
  const status = getTestResultStatusWithReview(test);

  switch (status) {
    case 'Pass':
      return 'Passed';
    case 'Fail':
      return 'Failed';
    case 'Error':
      return 'Error';
    default:
      return 'Unknown';
  }
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

/**
 * Checks if a test result has an execution error (no metrics to evaluate)
 *
 * @param test - The test result detail object
 * @returns True if the test has no metrics
 */
export function hasExecutionError(test: TestResultDetail): boolean {
  const metrics = test.test_metrics?.metrics || {};
  return Object.keys(metrics).length === 0;
}
