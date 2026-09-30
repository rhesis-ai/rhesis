import type { GridSortModel } from '@mui/x-data-grid';
import { nextSortModel } from '../useList';

const startedDesc = { by: 'start_time', order: 'desc' } as const;

describe('nextSortModel', () => {
  it('flips the default column when the grid clears it', () => {
    // The grid starts on start_time desc; its next click clears the sort.
    const prev: GridSortModel = [{ field: 'start_time', sort: 'desc' }];
    expect(nextSortModel(prev, [], startedDesc)).toEqual([
      { field: 'start_time', sort: 'asc' },
    ]);
  });

  it('keeps cycling the default column in both directions', () => {
    let model: GridSortModel = [{ field: 'start_time', sort: 'desc' }];
    model = nextSortModel(model, [], startedDesc);
    expect(model).toEqual([{ field: 'start_time', sort: 'asc' }]);
    model = nextSortModel(
      model,
      [{ field: 'start_time', sort: 'desc' }],
      startedDesc
    );
    expect(model).toEqual([{ field: 'start_time', sort: 'desc' }]);
    model = nextSortModel(model, [], startedDesc);
    expect(model).toEqual([{ field: 'start_time', sort: 'asc' }]);
  });

  it('falls back to the default when another column is cleared', () => {
    const prev: GridSortModel = [{ field: 'total_tokens', sort: 'desc' }];
    expect(nextSortModel(prev, [], startedDesc)).toEqual([
      { field: 'start_time', sort: 'desc' },
    ]);
  });

  it('passes a new sort through unchanged', () => {
    const prev: GridSortModel = [{ field: 'start_time', sort: 'desc' }];
    const model: GridSortModel = [{ field: 'total_tokens', sort: 'asc' }];
    expect(nextSortModel(prev, model, startedDesc)).toBe(model);
  });

  it('flips an asc default too', () => {
    const nameAsc = { by: 'name', order: 'asc' } as const;
    const prev: GridSortModel = [{ field: 'name', sort: 'desc' }];
    expect(nextSortModel(prev, [], nameAsc)).toEqual([
      { field: 'name', sort: 'asc' },
    ]);
  });
});
