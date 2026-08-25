import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineDirectory } from '@/utils/directory';
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

export const testSetsDirectory = defineDirectory({
  title: 'Test Sets',
  resource: 'test sets',
  capability: Capability.TestSet.READ,
  defaultPageSize: 25,
  filters: TEST_SETS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getTestSetsClient().getTestSets(params),
});
