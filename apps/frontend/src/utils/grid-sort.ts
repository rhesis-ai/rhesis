import type { GridSortModel } from '@mui/x-data-grid';

const GRID_TO_API_SORT_FIELD: Record<string, string> = {
  'counts.comments': 'comments_count',
  'counts.tasks': 'tasks_count',
  tags: 'tags_count',
};

export function gridSortToApiParams(sortModel: GridSortModel): {
  sort_by: string;
  sort_order: 'asc' | 'desc';
} {
  const active = sortModel[0];
  if (!active?.field || !active.sort) {
    return { sort_by: 'created_at', sort_order: 'desc' };
  }

  return {
    sort_by: GRID_TO_API_SORT_FIELD[active.field] ?? active.field,
    sort_order: active.sort,
  };
}

export const DEFAULT_GRID_SORT: GridSortModel = [
  { field: 'created_at', sort: 'desc' },
];
