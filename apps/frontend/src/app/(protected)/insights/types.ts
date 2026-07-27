export type InsightsTimeRange = '1d' | '7d' | '1m' | '3m';
export type InsightsRunFilterMode = 'timeRange' | 'testRuns';

export interface InsightsFilters {
  endpointId: string;
  /** Empty means all behaviors are visible. */
  behaviorIds: string[];
  /** Filter by time window or by explicit test runs — never both. */
  runFilterMode: InsightsRunFilterMode;
  timeRange: InsightsTimeRange;
  /**
   * Used when `runFilterMode` is `testRuns`. Empty means all test runs for the
   * endpoint.
   */
  testRunIds: string[];
}

export const DEFAULT_INSIGHTS_TIME_RANGE: InsightsTimeRange = '1m';

export const DEFAULT_INSIGHTS_FILTERS: InsightsFilters = {
  endpointId: '',
  behaviorIds: [],
  runFilterMode: 'timeRange',
  timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
  testRunIds: [],
};

const VALID_TIME_RANGES = new Set<InsightsTimeRange>(['1d', '7d', '1m', '3m']);

export function resolveInsightsTimeRange(
  timeRange: InsightsTimeRange | undefined
): InsightsTimeRange {
  if (timeRange && VALID_TIME_RANGES.has(timeRange)) {
    return timeRange;
  }
  return DEFAULT_INSIGHTS_TIME_RANGE;
}

export function normalizeInsightsFilters(
  filters: Partial<InsightsFilters> & {
    months?: number;
    /** Legacy field from the toolbar-only time range UI. */
    useDefaultTestRunWindow?: boolean;
  }
): InsightsFilters {
  let runFilterMode = filters.runFilterMode ?? 'timeRange';
  let timeRange = resolveInsightsTimeRange(filters.timeRange);
  let testRunIds = filters.testRunIds ?? [];

  if (
    typeof filters.months === 'number' &&
    filters.runFilterMode === undefined
  ) {
    const legacy: Partial<Record<number, InsightsTimeRange>> = {
      1: '1m',
      3: '3m',
    };
    timeRange = legacy[filters.months] ?? DEFAULT_INSIGHTS_TIME_RANGE;
    runFilterMode = 'timeRange';
    testRunIds = [];
  }

  if (
    filters.useDefaultTestRunWindow !== undefined &&
    filters.runFilterMode === undefined
  ) {
    runFilterMode = filters.useDefaultTestRunWindow ? 'timeRange' : 'testRuns';
    if (runFilterMode === 'timeRange') {
      testRunIds = [];
    }
  }

  return {
    endpointId: filters.endpointId ?? '',
    behaviorIds: filters.behaviorIds ?? [],
    runFilterMode,
    timeRange,
    testRunIds,
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
): Pick<
  import('@/utils/api-client/interfaces/common').TestResultsStatsOptions,
  'months' | 'start_date' | 'end_date'
> {
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
