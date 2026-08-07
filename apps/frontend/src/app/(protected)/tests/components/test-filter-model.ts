import type { GridFilterModel } from '@mui/x-data-grid';
import type { TestFilters } from './TestFilterDrawer';
import {
  appendPresenceFilterItems,
  stripPresenceFilterItems,
} from '@/components/common/presence-filter';

export const TEST_DRAWER_FILTER_FIELDS = [
  'test_type.type_value',
  'behavior.name',
  'category.name',
  'topic.name',
] as const;

export function applyQuickFilterToModel(
  prev: GridFilterModel,
  searchQuery: string
): GridFilterModel {
  const otherItems = prev.items.filter(item => item.field !== 'quickFilter');
  const items = searchQuery
    ? [
        ...otherItems,
        {
          id: 'quickFilter',
          field: 'quickFilter',
          operator: 'contains',
          value: searchQuery,
        },
      ]
    : otherItems;
  return { ...prev, items };
}

export function applyTestTypeFilterToModel(
  prev: GridFilterModel,
  typeFilter: string
): GridFilterModel {
  const otherItems = prev.items.filter(
    item => item.field !== 'test_type.type_value'
  );
  const items =
    typeFilter && typeFilter !== 'all'
      ? [
          ...otherItems,
          {
            id: 'test_type.type_value',
            field: 'test_type.type_value',
            operator: 'equals',
            value: typeFilter,
          },
        ]
      : otherItems;
  return { ...prev, items };
}

export function applyTestDrawerFiltersToModel(
  prev: GridFilterModel,
  drawerFilters: TestFilters
): GridFilterModel {
  const otherItems = stripPresenceFilterItems(
    prev.items.filter(
      item =>
        !TEST_DRAWER_FILTER_FIELDS.includes(
          item.field as (typeof TEST_DRAWER_FILTER_FIELDS)[number]
        )
    )
  );
  const drawerItems: GridFilterModel['items'] = [];

  if (drawerFilters.testType) {
    drawerItems.push({
      id: 'test_type.type_value',
      field: 'test_type.type_value',
      operator: 'equals',
      value: drawerFilters.testType,
    });
  }
  if (drawerFilters.behavior) {
    drawerItems.push({
      id: 'behavior.name',
      field: 'behavior.name',
      operator: 'equals',
      value: drawerFilters.behavior,
    });
  }
  if (drawerFilters.category) {
    drawerItems.push({
      id: 'category.name',
      field: 'category.name',
      operator: 'equals',
      value: drawerFilters.category,
    });
  }
  if (drawerFilters.topic) {
    drawerItems.push({
      id: 'topic.name',
      field: 'topic.name',
      operator: 'equals',
      value: drawerFilters.topic,
    });
  }

  return {
    ...prev,
    items: appendPresenceFilterItems([...otherItems, ...drawerItems], {
      tags: drawerFilters.tags,
      comments: drawerFilters.comments,
      tasks: drawerFilters.tasks,
    }),
  };
}

const INSIGHTS_FAILED_TEST_IDS_FIELD = 'insightsFailedTestIds';
const EMPTY_INSIGHTS_TEST_ID = '00000000-0000-0000-0000-000000000000';

function escapeODataValue(value: string): string {
  return value.replace(/'/g, "''");
}

export function buildTestIdsODataFilter(testIds: string[]): string {
  const ids = testIds.length > 0 ? testIds : [EMPTY_INSIGHTS_TEST_ID];
  const chunkSize = 40;
  const chunks: string[] = [];

  for (let i = 0; i < ids.length; i += chunkSize) {
    const slice = ids.slice(i, i + chunkSize);
    chunks.push(
      `(${slice.map(id => `id eq '${escapeODataValue(id)}'`).join(' or ')})`
    );
  }

  return chunks.length === 1 ? chunks[0] : `(${chunks.join(' or ')})`;
}

export function combineODataFilterExpressions(...parts: string[]): string {
  const expressions = parts.filter(Boolean);
  if (expressions.length === 0) return '';
  if (expressions.length === 1) return expressions[0];
  return expressions.map(expression => `(${expression})`).join(' and ');
}

export function applyInsightsFailedTestIdsToModel(
  prev: GridFilterModel,
  testIds: string[] | null
): GridFilterModel {
  const otherItems = prev.items.filter(
    item => item.field !== INSIGHTS_FAILED_TEST_IDS_FIELD && item.field !== 'id'
  );

  if (testIds === null) {
    return { ...prev, items: otherItems };
  }

  const value = testIds.length > 0 ? testIds : [EMPTY_INSIGHTS_TEST_ID];

  return {
    ...prev,
    items: [
      ...otherItems,
      {
        field: 'id',
        operator: 'isAnyOf',
        value,
      },
    ],
  };
}
