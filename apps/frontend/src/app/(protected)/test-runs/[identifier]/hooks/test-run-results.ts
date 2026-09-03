import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';

/**
 * Server-safe fetchers for a run's test results -- no React import, so
 * `page.tsx` (a Server Component) can call `fetchSmallTestRunResults`
 * directly without pulling the client-only `useTestRunDetailData` hook
 * into its module graph.
 */

export async function fetchAllTestResults(
  testRunId: string
): Promise<TestResultDetail[]> {
  const testResultsClient = new ApiClientFactory().getTestResultsClient();

  let testResults: TestResultDetail[] = [];
  let skip = 0;
  const batchSize = 100;
  let hasMore = true;

  while (hasMore) {
    const response = await testResultsClient.getTestResults({
      filter: `test_run_id eq '${testRunId}'`,
      limit: batchSize,
      skip,
      sort_by: 'created_at',
      sort_order: 'desc',
      stripConversation: true,
    });

    testResults = [...testResults, ...response.data];
    const totalCount = response.pagination?.totalCount || 0;
    hasMore = testResults.length < totalCount;
    skip += batchSize;

    if (skip > 10000) break;
  }

  return testResults;
}

/**
 * Server-side prefetch: the run's results when one page holds them all,
 * otherwise `undefined`. Rendering the page shouldn't wait on tens of
 * sequential requests for a big run; the client loads those as before.
 */
export async function fetchSmallTestRunResults(
  factory: ApiClientFactory,
  testRunId: string
): Promise<TestResultDetail[] | undefined> {
  const response = await factory.getTestResultsClient().getTestResults({
    filter: `test_run_id eq '${testRunId}'`,
    limit: 100,
    skip: 0,
    sort_by: 'created_at',
    sort_order: 'desc',
    stripConversation: true,
  });
  const totalCount = response.pagination?.totalCount || 0;
  return response.data.length < totalCount ? undefined : response.data;
}
