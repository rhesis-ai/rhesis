import {
  normalizeInsightsFilters,
  resolveInsightsTimeRange,
  timeRangeToStatsParams,
  type InsightsTimeRange,
} from '../types';

describe('resolveInsightsTimeRange', () => {
  it('defaults to 1m', () => {
    expect(resolveInsightsTimeRange(undefined)).toBe('1m');
    expect(resolveInsightsTimeRange('invalid' as InsightsTimeRange)).toBe('1m');
  });
});

describe('normalizeInsightsFilters', () => {
  it('migrates legacy months field to 1m', () => {
    expect(normalizeInsightsFilters({ months: 1, endpointId: 'ep-1' })).toEqual(
      {
        timeRange: '1m',
        endpointId: 'ep-1',
      }
    );
  });
});

describe('timeRangeToStatsParams', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2026-06-24T12:00:00.000Z'));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it.each<[InsightsTimeRange, object]>([
    ['1m', { months: 1 }],
    ['3m', { months: 3 }],
  ])('maps %s to months param', (range, expected) => {
    expect(timeRangeToStatsParams(range)).toEqual(expected);
  });

  it('maps 1d to a one-day date range', () => {
    expect(timeRangeToStatsParams('1d')).toEqual({
      start_date: '2026-06-23T12:00:00.000Z',
      end_date: '2026-06-24T12:00:00.000Z',
    });
  });

  it('maps 7d to a seven-day date range', () => {
    expect(timeRangeToStatsParams('7d')).toEqual({
      start_date: '2026-06-17T12:00:00.000Z',
      end_date: '2026-06-24T12:00:00.000Z',
    });
  });
});
