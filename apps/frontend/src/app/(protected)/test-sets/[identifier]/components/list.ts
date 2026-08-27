import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';
import { TESTS_FILTERS } from '@/app/(protected)/tests/components/list';

/**
 * The embedded "tests in this test set" grid: same filter surface as the main
 * tests list, but scoped to one test set's nested endpoint. Defaults to the
 * topic ordering the detail page has always shown; sortable interactively
 * from there like any other EntityGrid-backed list.
 */
export function testSetTestsList(testSetId: string) {
  return defineList<TestDetail, typeof TESTS_FILTERS>({
    title: 'Tests',
    resource: 'tests',
    capability: Capability.Test.READ,
    defaultPageSize: 25,
    defaultSort: { by: 'topic.name', order: 'asc' },
    filters: TESTS_FILTERS,
    list: (factory: ApiClientFactory, params) =>
      factory.getTestSetsClient().getTestSetTests(testSetId, params),
  });
}
