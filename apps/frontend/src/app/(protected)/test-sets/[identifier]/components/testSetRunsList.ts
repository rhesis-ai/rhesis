import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';
import { escapeODataValue } from '@/utils/odata-filter';

const SCOPED_FILTERS = {
  search: {
    kind: 'search',
    columns: ['name', 'user/name', 'status/name'],
    navs: [{ nav: '_tags_relationship', columns: ['tag/name'] }],
  },
  status: { kind: 'enum', column: 'status/name' },
} as const;

export function testSetRunsList(testSetId: string) {
  const scopeFilter = `test_configuration/test_set/id eq '${escapeODataValue(testSetId)}'`;

  return defineList<TestRunDetail, typeof SCOPED_FILTERS>({
    title: 'Test Runs',
    resource: 'test runs',
    capability: Capability.TestRun.READ,
    defaultPageSize: 25,
    filters: SCOPED_FILTERS,
    list: (factory: ApiClientFactory, params) => {
      const { $filter, ...rest } = params;
      const combined = $filter
        ? `(${$filter}) and (${scopeFilter})`
        : scopeFilter;
      return factory
        .getTestRunsClient()
        .getTestRuns({ ...rest, filter: combined });
    },
  });
}
