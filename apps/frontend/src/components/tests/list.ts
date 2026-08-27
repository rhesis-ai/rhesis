import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestSet } from '@/utils/api-client/interfaces/test-set';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

export const LINKED_TEST_SETS_FILTERS = {} as const;

/** The test sets one test belongs to (the test detail page's Linked Test Sets tab). */
export function linkedTestSetsList(testId: string) {
  return defineList<TestSet, typeof LINKED_TEST_SETS_FILTERS>({
    title: 'Linked Test Sets',
    resource: 'test sets',
    capability: Capability.TestSet.READ,
    defaultPageSize: 10,
    filters: LINKED_TEST_SETS_FILTERS,
    list: (factory: ApiClientFactory, params) =>
      factory.getTestsClient().getLinkedTestSets(testId, params),
  });
}
