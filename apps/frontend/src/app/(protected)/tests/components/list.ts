import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestDetail } from '@/utils/api-client/interfaces/tests';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

/** `value` is a `PresenceFilterValue` ('all'/'with'/'without') at every call site. */
function presenceClause(
  relationship: string,
  value: string
): string | undefined {
  if (value === 'with') return `${relationship}/any()`;
  if (value === 'without') return `not ${relationship}/any()`;
  return undefined;
}

/** Shared with the embedded test-set tests grid, which filters the same entity. */
export const TESTS_FILTERS = {
  search: {
    kind: 'search',
    columns: [
      'prompt/content',
      'requirement/name',
      'topic/name',
      'category/name',
    ],
    navs: [{ nav: '_tags_relationship', columns: ['tag/name'] }],
  },
  testType: { kind: 'enum', column: 'test_type/type_value' },
  requirement: { kind: 'enum', column: 'requirement/name' },
  category: { kind: 'enum', column: 'category/name' },
  topic: { kind: 'enum', column: 'topic/name' },
  tagsPresence: {
    kind: 'raw',
    toOData: (value: string) => presenceClause('_tags_relationship', value),
  },
  commentsPresence: {
    kind: 'raw',
    toOData: (value: string) => presenceClause('comments', value),
  },
  tasksPresence: {
    kind: 'raw',
    toOData: (value: string) => presenceClause('tasks', value),
  },
} as const;

/**
 * SSR-prefetched except for the "insights failed tests" deep link: that path's
 * extra ID filter resolves asynchronously on the client, after first render,
 * so `tests/page.tsx` skips the prefetch when its search params are present.
 */
export const testsList = defineList<TestDetail, typeof TESTS_FILTERS>({
  title: 'Tests',
  resource: 'tests',
  capability: Capability.Test.READ,
  defaultPageSize: 25,
  filters: TESTS_FILTERS,
  list: (factory: ApiClientFactory, params) => {
    const { $filter, ...rest } = params;
    return factory.getTestsClient().getTests({ ...rest, filter: $filter });
  },
  delete: {
    bulk: (factory: ApiClientFactory, ids: string[]) =>
      factory.getTestsClient().bulkDeleteTests(ids),
    capability: Capability.Test.DELETE,
    capabilityMode: 'ambient',
    labelSingular: 'test',
    labelPlural: 'tests',
    confirmMessage: count =>
      count === 1
        ? 'Are you sure you want to delete this test? Related data will not be deleted.'
        : `Are you sure you want to delete ${count} tests? Don't worry, related data will not be deleted, only these records.`,
  },
});
