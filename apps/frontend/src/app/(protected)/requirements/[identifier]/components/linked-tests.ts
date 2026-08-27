import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';

/** Every test linked to a requirement, newest first. Shared by server prefetch and client. */
export function fetchRequirementLinkedTests(
  factory: ApiClientFactory,
  requirementId: string
): Promise<TestDetail[]> {
  return factory.getTestsClient().getAllTests({
    filter: `requirement_id eq '${requirementId.replace(/'/g, "''")}'`,
    sort_by: 'created_at',
    sort_order: 'desc',
  });
}
