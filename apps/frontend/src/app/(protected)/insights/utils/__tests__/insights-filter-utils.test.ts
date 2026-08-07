import {
  checkedIdsFromFilter,
  checkedIdsFromOptionalFilter,
  idsFromCheckedSelection,
  idsFromCheckedSelectionOptional,
  isOptionalFilterActive,
  isRunFilterActive,
} from '../insights-filter-utils';

describe('insights-filter-utils', () => {
  it('treats empty filter as all checked in drawer', () => {
    expect(checkedIdsFromFilter(['b1', 'b2'], [])).toEqual(['b1', 'b2']);
  });

  it('stores empty selection when everything remains checked', () => {
    expect(idsFromCheckedSelection(['b1', 'b2'], ['b1', 'b2'])).toEqual([]);
  });

  it('stores subset when only some items remain checked', () => {
    expect(idsFromCheckedSelection(['b1', 'b2', 'b3'], ['b2'])).toEqual(['b2']);
  });

  describe('checkedIdsFromOptionalFilter / idsFromCheckedSelectionOptional', () => {
    it('treats an unset (null) filter as everything checked', () => {
      expect(checkedIdsFromOptionalFilter(['b1', 'b2'], null)).toEqual([
        'b1',
        'b2',
      ]);
    });

    it('checking everything collapses back to null (no filter)', () => {
      expect(
        idsFromCheckedSelectionOptional(['b1', 'b2'], ['b1', 'b2'])
      ).toBeNull();
    });

    it('unchecking everything is a real, distinct empty-array state', () => {
      expect(idsFromCheckedSelectionOptional(['b1', 'b2'], [])).toEqual([]);
    });

    it('an explicit empty selection renders as nothing checked, not everything', () => {
      expect(checkedIdsFromOptionalFilter(['b1', 'b2'], [])).toEqual([]);
    });

    it('a subset selection is preserved as-is', () => {
      expect(
        idsFromCheckedSelectionOptional(['b1', 'b2', 'b3'], ['b2'])
      ).toEqual(['b2']);
    });
  });

  describe('isOptionalFilterActive', () => {
    it('is inactive when null (no filter)', () => {
      expect(isOptionalFilterActive(null)).toBe(false);
    });

    it('is active when explicitly filtered to nothing', () => {
      expect(isOptionalFilterActive([])).toBe(true);
    });

    it('is active for a real subset', () => {
      expect(isOptionalFilterActive(['b1'])).toBe(true);
    });
  });

  describe('isRunFilterActive', () => {
    it('is inactive for the default time range with no explicit runs', () => {
      expect(
        isRunFilterActive({
          timeRange: 'always',
          testRunIds: [],
        })
      ).toBe(false);
    });

    it('is active for non-default time ranges', () => {
      expect(
        isRunFilterActive({
          timeRange: '7d',
          testRunIds: [],
        })
      ).toBe(true);
    });

    it('is active when specific test runs are selected', () => {
      expect(
        isRunFilterActive({
          timeRange: 'always',
          testRunIds: ['run-1'],
        })
      ).toBe(true);
    });
  });
});
