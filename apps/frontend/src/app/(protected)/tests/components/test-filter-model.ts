import type { GridFilterModel } from '@mui/x-data-grid';
import type { TestFilters } from './TestFilterDrawer';
import {
  appendPresenceFilterItems,
  stripPresenceFilterItems,
} from '@/components/common/presence-filter';

export const TEST_DRAWER_FILTER_FIELDS = [
  'test_type.type_value',
  'status.name',
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
        { field: 'quickFilter', operator: 'contains', value: searchQuery },
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
      field: 'test_type.type_value',
      operator: 'equals',
      value: drawerFilters.testType,
    });
  }
  if (drawerFilters.status) {
    drawerItems.push({
      field: 'status.name',
      operator: 'contains',
      value: drawerFilters.status,
    });
  }
  if (drawerFilters.behavior) {
    drawerItems.push({
      field: 'behavior.name',
      operator: 'contains',
      value: drawerFilters.behavior,
    });
  }
  if (drawerFilters.category) {
    drawerItems.push({
      field: 'category.name',
      operator: 'contains',
      value: drawerFilters.category,
    });
  }
  if (drawerFilters.topic) {
    drawerItems.push({
      field: 'topic.name',
      operator: 'contains',
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
