import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';
import { escapeODataValue } from '@/utils/odata-filter';

function containsClause(column: string, value: string): string | undefined {
  return value.trim()
    ? `contains(tolower(${column}),tolower('${escapeODataValue(value.trim())}'))`
    : undefined;
}

/** `value` is a `PresenceFilterValue` ('all'/'with'/'without') at every call site. */
function presenceClause(
  relationship: string,
  value: string
): string | undefined {
  if (value === 'with') return `${relationship}/any()`;
  if (value === 'without') return `not ${relationship}/any()`;
  return undefined;
}

const TEST_SETS_FILTERS = {
  search: {
    kind: 'search',
    columns: ['name', 'user/name', 'test_set_type/type_value'],
    navs: [{ nav: '_tags_relationship', columns: ['tag/name'] }],
  },
  testSetType: { kind: 'enum', column: 'test_set_type/type_value' },
  status: {
    kind: 'raw',
    toOData: (value: string) => containsClause('status/name', value),
  },
  creator: {
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
} as const;

export const testSetsList = defineList({
  title: 'Test Sets',
  resource: 'test sets',
  capability: Capability.TestSet.READ,
  defaultPageSize: 25,
  filters: TEST_SETS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getTestSetsClient().getTestSets(params),
  delete: {
    bulk: (factory: ApiClientFactory, ids: string[]) =>
      factory.getTestSetsClient().bulkDeleteTestSets(ids),
    capability: Capability.TestSet.DELETE,
    capabilityMode: 'ambient',
    labelSingular: 'test set',
    labelPlural: 'test sets',
    confirmMessage: count =>
      count === 1
        ? 'Are you sure you want to delete this test set? Related data will not be deleted.'
        : `Are you sure you want to delete ${count} test sets? Don't worry, related data will not be deleted, only these records.`,
  },
});
