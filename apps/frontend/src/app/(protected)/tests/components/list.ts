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

const TESTS_FILTERS = {
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
 * Not SSR-prefetched: this page's "insights failed tests" deep link (search
 * params opened from the Insights page) adds an extra ID filter resolved
 * asynchronously on the client, after first render. Server-rendered
 * `initialData` would show the unfiltered list first, then swap -- worse
 * than the existing client-only loading state for that path.
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
});
