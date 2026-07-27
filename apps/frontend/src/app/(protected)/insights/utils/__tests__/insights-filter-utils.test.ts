import {
  behaviorIdsFromCheckedSelection,
  checkedBehaviorIdsFromFilter,
  filterColumnsByBehaviorIds,
  isRunFilterActive,
} from '../insights-filter-utils';

describe('insights-filter-utils', () => {
  const columns = [
    { id: 'b1', name: 'Safety' },
    { id: 'b2', name: 'Fluency' },
    { id: 'b3', name: 'Tone' },
  ];

  it('shows all columns when behaviorIds is empty', () => {
    expect(filterColumnsByBehaviorIds(columns, [])).toEqual(columns);
  });

  it('filters columns to selected behavior ids', () => {
    expect(filterColumnsByBehaviorIds(columns, ['b1', 'b3'])).toEqual([
      { id: 'b1', name: 'Safety' },
      { id: 'b3', name: 'Tone' },
    ]);
  });

  it('treats empty filter as all checked in drawer', () => {
    expect(checkedBehaviorIdsFromFilter(['b1', 'b2'], [])).toEqual([
      'b1',
      'b2',
    ]);
  });

  it('stores empty behaviorIds when all behaviors remain checked', () => {
    expect(behaviorIdsFromCheckedSelection(['b1', 'b2'], ['b1', 'b2'])).toEqual(
      []
    );
  });

  it('stores subset when only some behaviors remain checked', () => {
    expect(behaviorIdsFromCheckedSelection(['b1', 'b2', 'b3'], ['b2'])).toEqual(
      ['b2']
    );
  });

  describe('isRunFilterActive', () => {
    it('is inactive for default time range mode', () => {
      expect(
        isRunFilterActive({
          runFilterMode: 'timeRange',
          timeRange: '1m',
          testRunIds: [],
        })
      ).toBe(false);
    });

    it('is active for non-default time ranges', () => {
      expect(
        isRunFilterActive({
          runFilterMode: 'timeRange',
          timeRange: '7d',
          testRunIds: [],
        })
      ).toBe(true);
    });

    it('is active for testRuns mode even with empty allowlist', () => {
      expect(
        isRunFilterActive({
          runFilterMode: 'testRuns',
          timeRange: '1m',
          testRunIds: [],
        })
      ).toBe(true);
    });
  });
});
