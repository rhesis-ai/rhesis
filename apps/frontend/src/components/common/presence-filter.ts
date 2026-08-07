import type { GridFilterModel } from '@mui/x-data-grid';

export type PresenceFilterValue = 'all' | 'with' | 'without';

export const PRESENCE_FILTER_FIELDS = ['tags', 'comments', 'tasks'] as const;
export type PresenceFilterField = (typeof PRESENCE_FILTER_FIELDS)[number];

export interface ActivityPresenceFilters {
  tags: PresenceFilterValue;
  comments: PresenceFilterValue;
  tasks: PresenceFilterValue;
  /** Optional — only used on test run grids with child-result review activity. */
  reviews?: PresenceFilterValue;
}

export const EMPTY_ACTIVITY_PRESENCE_FILTERS: ActivityPresenceFilters = {
  tags: 'all',
  comments: 'all',
  tasks: 'all',
};

export function stripPresenceFilterItems(
  items: GridFilterModel['items']
): GridFilterModel['items'] {
  return items.filter(
    item => !PRESENCE_FILTER_FIELDS.includes(item.field as PresenceFilterField)
  );
}

export function presenceToFilterItem(
  field: PresenceFilterField,
  value: PresenceFilterValue
): GridFilterModel['items'][number] | null {
  if (value === 'all') return null;
  return {
    id: `${field}-presence`,
    field,
    operator: value === 'with' ? 'isNotEmpty' : 'isEmpty',
    value: true,
  };
}

export function appendPresenceFilterItems(
  items: GridFilterModel['items'],
  filters: ActivityPresenceFilters
): GridFilterModel['items'] {
  const next = [...items];
  for (const field of PRESENCE_FILTER_FIELDS) {
    const item = presenceToFilterItem(field, filters[field]);
    if (item) next.push(item);
  }
  return next;
}

export function hasActivePresenceFilters(
  filters: ActivityPresenceFilters
): boolean {
  return (
    filters.tags !== 'all' ||
    filters.comments !== 'all' ||
    filters.tasks !== 'all' ||
    (filters.reviews !== undefined && filters.reviews !== 'all')
  );
}

export function countActivePresenceFilters(
  filters: ActivityPresenceFilters
): number {
  return (
    (filters.tags !== 'all' ? 1 : 0) +
    (filters.comments !== 'all' ? 1 : 0) +
    (filters.tasks !== 'all' ? 1 : 0) +
    (filters.reviews !== undefined && filters.reviews !== 'all' ? 1 : 0)
  );
}
