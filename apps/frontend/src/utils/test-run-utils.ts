import { TestRunsClient } from '@/utils/api-client/test-runs-client';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

interface PollForTestRunOptions {
  /** Maximum number of polling attempts (default: 10) */
  maxAttempts?: number;
  /** Initial delay in milliseconds before first attempt (default: 500) */
  initialDelay?: number;
  /** Whether to enable exponential backoff (default: true) */
  exponentialBackoff?: boolean;
}

/**
 * Polls for a test run created by a test configuration execution.
 * Uses exponential backoff to handle the delay between test configuration
 * execution and test run creation by the worker.
 *
 * @param testRunsClient - The TestRunsClient instance to use for API calls
 * @param testConfigurationId - The ID of the test configuration
 * @param options - Optional polling configuration
 * @returns The test run if found, or null if not found after all attempts
 */
export async function pollForTestRun(
  testRunsClient: TestRunsClient,
  testConfigurationId: string,
  options: PollForTestRunOptions = {}
): Promise<TestRunDetail | null> {
  const {
    maxAttempts = 10,
    initialDelay = 500,
    exponentialBackoff = true,
  } = options;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    // Calculate delay with exponential backoff: 500ms, 1s, 2s, 4s, etc.
    const delay = exponentialBackoff
      ? initialDelay * Math.pow(2, attempt)
      : initialDelay;

    // Wait before attempting (skip delay on first attempt)
    if (attempt > 0) {
      await new Promise(resolve => setTimeout(resolve, delay));
    }

    try {
      const testRunsResponse =
        await testRunsClient.getTestRunsByTestConfiguration(
          testConfigurationId,
          { limit: 1, sort_by: 'created_at', sort_order: 'desc' }
        );

      if (testRunsResponse.data && testRunsResponse.data.length > 0) {
        return testRunsResponse.data[0];
      }
    } catch (error) {
      // Log warning but continue retrying (except on last attempt)
      if (attempt === maxAttempts - 1) {
        console.warn(
          `Failed to fetch test run after ${maxAttempts} attempts:`,
          error
        );
      }
      // Continue to next attempt
    }
  }

  // Test run not found after all attempts
  return null;
}
