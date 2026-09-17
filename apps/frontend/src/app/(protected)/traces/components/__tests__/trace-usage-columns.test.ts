import { gridSortToApiParams } from '@/utils/grid-sort';

/**
 * The traces grid and the test runs grid must name the same figure the same way, and
 * both must map onto a sort field the telemetry API actually accepts. A mismatch here is
 * silent: the grid sends a field the backend rejects, or sorts by the wrong one.
 */
describe('trace usage column sorting', () => {
  const TRACE_COLUMNS = [
    'total_tokens',
    'total_input_tokens',
    'total_output_tokens',
    'total_cost_usd',
    'total_input_cost_usd',
    'total_output_cost_usd',
    'models',
  ];

  // Mirrors TRACE_SORT_FIELDS in apps/backend/.../crud/telemetry.py.
  const ACCEPTED_BY_API = [
    'total_tokens',
    'total_input_tokens',
    'total_output_tokens',
    'total_cost_usd',
    'total_input_cost_usd',
    'total_output_cost_usd',
    'model',
  ];

  it('maps each column onto a field the API accepts', () => {
    const mapped = TRACE_COLUMNS.map(
      field => gridSortToApiParams([{ field, sort: 'desc' }]).sort_by
    );

    expect(mapped).toEqual(ACCEPTED_BY_API);
  });

  it('sends the models column as the singular sort field', () => {
    // The row carries a list; the backend orders by its alphabetically first entry.
    expect(gridSortToApiParams([{ field: 'models', sort: 'asc' }])).toEqual({
      sort_by: 'model',
      sort_order: 'asc',
    });
  });

  it('agrees with the test runs grid on the same figures', () => {
    const fromTestRuns = TRACE_COLUMNS.map(
      field =>
        gridSortToApiParams([
          {
            field: field === 'models' ? 'usage.models' : `usage.${field}`,
            sort: 'desc',
          },
        ]).sort_by
    );

    expect(fromTestRuns).toEqual(ACCEPTED_BY_API);
  });

  it('passes the sort direction through unchanged', () => {
    expect(
      gridSortToApiParams([{ field: 'total_input_cost_usd', sort: 'asc' }])
    ).toEqual({ sort_by: 'total_input_cost_usd', sort_order: 'asc' });
  });
});
