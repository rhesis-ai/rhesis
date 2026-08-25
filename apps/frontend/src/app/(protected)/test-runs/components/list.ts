import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TestRunDetail } from '@/utils/api-client/interfaces/test-run';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';
import { escapeODataValue } from '@/utils/odata-filter';

/** `value` is a `PresenceFilterValue` ('all'/'with'/'without') at every call site. */
function presenceClause(
  relationship: string,
  value: string
): string | undefined {
  if (value === 'with') return `${relationship}/any()`;
  if (value === 'without') return `not ${relationship}/any()`;
  return undefined;
}

function containsClause(column: string, value: string): string | undefined {
  return value.trim()
    ? `contains(tolower(${column}),tolower('${escapeODataValue(value.trim())}'))`
    : undefined;
}

const TEST_RUNS_FILTERS = {
  search: {
    kind: 'search',
    columns: [
      'name',
      'test_configuration/test_set/name',
      'user/name',
      'status/name',
    ],
    navs: [{ nav: '_tags_relationship', columns: ['tag/name'] }],
  },
  status: { kind: 'enum', column: 'status/name' },
  testSet: {
    kind: 'raw',
    toOData: (value: string) =>
      containsClause('test_configuration/test_set/name', value),
  },
  executor: {
    kind: 'raw',
    toOData: (value: string) => containsClause('user/name', value),
  },
  tag: {
    kind: 'raw',
    toOData: (value: string) =>
      value.trim()
        ? `_tags_relationship/any(x: contains(tolower(x/tag/name),tolower('${escapeODataValue(value.trim())}')))`
        : undefined,
  },
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
  // Not OData -- surfaced as `has_experiment`/`has_reviews` top-level params via `extraParams`.
  runKind: { kind: 'raw', toOData: () => undefined },
  reviews: { kind: 'raw', toOData: () => undefined },
} as const;

export const testRunsList = defineList<TestRunDetail, typeof TEST_RUNS_FILTERS>(
  {
    title: 'Test Runs',
    resource: 'test runs',
    capability: Capability.TestRun.READ,
    defaultPageSize: 50,
    filters: TEST_RUNS_FILTERS,
    extraParams: filters => ({
      ...(filters.runKind === 'tests' ? { has_experiment: false } : {}),
      ...(filters.runKind === 'experiments' ? { has_experiment: true } : {}),
      ...(filters.reviews === 'with' ? { has_reviews: true } : {}),
      ...(filters.reviews === 'without' ? { has_reviews: false } : {}),
    }),
    list: (factory: ApiClientFactory, params) => {
      const { $filter, ...rest } = params;
      return factory
        .getTestRunsClient()
        .getTestRuns({ ...rest, filter: $filter });
    },
  }
);
