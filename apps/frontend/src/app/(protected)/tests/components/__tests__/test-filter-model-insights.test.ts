import type { GridFilterModel } from '@mui/x-data-grid';
import {
  applyInsightsFailedTestIdsToModel,
  buildTestIdsODataFilter,
  combineODataFilterExpressions,
} from '../test-filter-model';

describe('applyInsightsFailedTestIdsToModel', () => {
  const emptyModel: GridFilterModel = { items: [] };

  it('adds id isAnyOf filter when test ids are provided', () => {
    const result = applyInsightsFailedTestIdsToModel(emptyModel, [
      'test-1',
      'test-2',
    ]);
    expect(result.items).toEqual([
      {
        field: 'id',
        operator: 'isAnyOf',
        value: ['test-1', 'test-2'],
      },
    ]);
  });

  it('clears insights filter when null', () => {
    const withFilter = applyInsightsFailedTestIdsToModel(emptyModel, [
      'test-1',
    ]);
    const cleared = applyInsightsFailedTestIdsToModel(withFilter, null);
    expect(cleared.items).toEqual([]);
  });
});

describe('buildTestIdsODataFilter', () => {
  it('builds id eq expression for test ids', () => {
    expect(buildTestIdsODataFilter(['test-1', 'test-2'])).toBe(
      "(id eq 'test-1' or id eq 'test-2')"
    );
  });

  it('uses empty sentinel when no ids are provided', () => {
    expect(buildTestIdsODataFilter([])).toBe(
      "(id eq '00000000-0000-0000-0000-000000000000')"
    );
  });
});

describe('combineODataFilterExpressions', () => {
  it('joins expressions with and', () => {
    expect(
      combineODataFilterExpressions(
        "status/name eq 'Failed'",
        "(id eq 'test-1' or id eq 'test-2')"
      )
    ).toBe(
      "(status/name eq 'Failed') and ((id eq 'test-1' or id eq 'test-2'))"
    );
  });
});
