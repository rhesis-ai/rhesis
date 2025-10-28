/**
 * Utility functions for determining test result status
 */

import { TestResultDetail } from './api-client/interfaces/test-results';
import { TestResultStatus } from '@/components/common/StatusChip';

/**
 * Determines the test result status from a test result object
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
    (metric) => metric.is_successful
  ).length;
  
  // All metrics passed = Pass, otherwise Fail
  return passedMetrics === metricsCount ? 'Pass' : 'Fail';
}

/**
 * Gets the label text for a test result status
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
 * Checks if a test result has an execution error (no metrics to evaluate)
 * 
 * @param test - The test result detail object
 * @returns True if the test has no metrics
 */
export function hasExecutionError(test: TestResultDetail): boolean {
  const metrics = test.test_metrics?.metrics || {};
  return Object.keys(metrics).length === 0;
}

