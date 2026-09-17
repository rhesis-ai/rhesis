import { gridSortToApiParams } from '../grid-sort';

/**
 * The grid names a column after the row path it reads; the API names the same
 * thing after the figure it orders by. An unmapped field is sent through as-is
 * and rejected by the backend's sort validation, so every sortable column whose
 * two names differ needs an entry here.
 */
describe('gridSortToApiParams', () => {
  it('maps the activity counts to their virtual sort fields', () => {
    expect(
      gridSortToApiParams([{ field: 'counts.annotated_tests', sort: 'desc' }])
    ).toEqual({ sort_by: 'annotated_tests_count', sort_order: 'desc' });
    expect(
      gridSortToApiParams([{ field: 'counts.comments', sort: 'asc' }])
    ).toEqual({ sort_by: 'comments_count', sort_order: 'asc' });
    expect(
      gridSortToApiParams([{ field: 'counts.tasks', sort: 'asc' }])
    ).toEqual({ sort_by: 'tasks_count', sort_order: 'asc' });
    expect(gridSortToApiParams([{ field: 'tags', sort: 'asc' }])).toEqual({
      sort_by: 'tags_count',
      sort_order: 'asc',
    });
  });

  it('passes a column whose name already matches the API through unchanged', () => {
    expect(gridSortToApiParams([{ field: 'name', sort: 'asc' }])).toEqual({
      sort_by: 'name',
      sort_order: 'asc',
    });
  });

  it('falls back to newest first when nothing is sorted', () => {
    expect(gridSortToApiParams([])).toEqual({
      sort_by: 'created_at',
      sort_order: 'desc',
    });
  });
});
