import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';

export type InsightsTimeRange = '1d' | '7d' | '1m' | '3m';

export interface InsightsFilters {
  timeRange: InsightsTimeRange;
  endpointId: string;
}

export const DEFAULT_INSIGHTS_TIME_RANGE: InsightsTimeRange = '1m';

export const DEFAULT_INSIGHTS_FILTERS: InsightsFilters = {
  timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
  endpointId: '',
};

const VALID_TIME_RANGES = new Set<InsightsTimeRange>(['1d', '7d', '1m', '3m']);

/** Ensure the toolbar always has a valid selection (defaults to 1M). */
export function resolveInsightsTimeRange(
  timeRange: InsightsTimeRange | undefined
): InsightsTimeRange {
  if (timeRange && VALID_TIME_RANGES.has(timeRange)) {
    return timeRange;
  }
  return DEFAULT_INSIGHTS_TIME_RANGE;
}

export function normalizeInsightsFilters(
  filters: Partial<InsightsFilters> & { months?: number }
): InsightsFilters {
  let timeRange = filters.timeRange;
  if (!timeRange && typeof filters.months === 'number') {
    const legacy: Partial<Record<number, InsightsTimeRange>> = {
      1: '1m',
      3: '3m',
    };
    timeRange = legacy[filters.months];
  }
  return {
    timeRange: resolveInsightsTimeRange(timeRange),
    endpointId: filters.endpointId ?? '',
  };
}

export const INSIGHTS_TIME_RANGE_OPTIONS: {
  value: InsightsTimeRange;
  label: string;
}[] = [
  { value: '1d', label: '1D' },
  { value: '7d', label: '7D' },
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
];

function toIsoDate(date: Date): string {
  return date.toISOString();
}

/** Map UI time-range pills to stats API query parameters. */
export function timeRangeToStatsParams(
  timeRange: InsightsTimeRange
): Pick<TestResultsStatsOptions, 'months' | 'start_date' | 'end_date'> {
  switch (timeRange) {
    case '1d': {
      const end = new Date();
      const start = new Date(end);
      start.setUTCDate(start.getUTCDate() - 1);
      return { start_date: toIsoDate(start), end_date: toIsoDate(end) };
    }
    case '7d': {
      const end = new Date();
      const start = new Date(end);
      start.setUTCDate(start.getUTCDate() - 7);
      return { start_date: toIsoDate(start), end_date: toIsoDate(end) };
    }
    case '1m':
      return { months: 1 };
    case '3m':
      return { months: 3 };
  }
}
