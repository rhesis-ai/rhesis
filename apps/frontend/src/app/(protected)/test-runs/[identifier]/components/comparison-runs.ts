import type { ApiClientFactory } from '@/utils/api-client/client-factory';

/** Whether the test set has at least one other run to compare `testRunId` with. */
export async function hasOtherRunsForTestSet(
  factory: ApiClientFactory,
  testSetId: string,
  testRunId: string
): Promise<boolean> {
  const response = await factory.getTestRunsClient().getTestRuns({
    limit: 2,
    skip: 0,
    sort_by: 'created_at',
    sort_order: 'desc',
    filter: `test_configuration/test_set/id eq '${testSetId}'`,
  });
  return response.data.some(run => run.id !== testRunId);
}
