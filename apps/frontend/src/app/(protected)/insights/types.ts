export type InsightsTimeRange = 'always' | '1d' | '7d' | '1m' | '3m';
export type InsightsRunFilterMode = 'timeRange' | 'testRuns';

export interface InsightsFilters {
  endpointId: string;
  /**
   * `null` = no filter (default, all behaviors visible). `[]` is a real,
   * distinct state — the user explicitly unchecked every behavior, so
   * nothing should show. A plain `string[]` can't represent "explicitly
   * none" without colliding with "no filter", which is why this is
   * nullable.
   */
  behaviorIds: string[] | null;
  /** Same `null`/`[]`/`[...]` convention as `behaviorIds`. */
  statusIds: string[] | null;
  /** Narrows which test runs are in scope; testRunIds further narrows within it. */
  timeRange: InsightsTimeRange;
  /**
   * Explicit test runs to narrow down to, within `timeRange`. Empty means all
   * test runs in that window.
   */
  testRunIds: string[];
  /**
   * Derived from `testRunIds` (non-empty → 'testRuns') by
   * `normalizeInsightsFilters` — not independently settable. Kept for
   * consumers (drill-down URLs, cache keys, labels) that describe the scope
   * as one of two modes.
   */
  runFilterMode: InsightsRunFilterMode;
}

export const DEFAULT_INSIGHTS_TIME_RANGE: InsightsTimeRange = 'always';

export const DEFAULT_INSIGHTS_FILTERS: InsightsFilters = {
  endpointId: '',
  behaviorIds: null,
  statusIds: null,
  runFilterMode: 'timeRange',
  timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
  testRunIds: [],
};

const VALID_TIME_RANGES = new Set<InsightsTimeRange>([
  'always',
  '1d',
  '7d',
  '1m',
  '3m',
]);

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
    testRunIds = [];
  }

  if (
    filters.useDefaultTestRunWindow !== undefined &&
    filters.runFilterMode === undefined &&
    filters.useDefaultTestRunWindow
  ) {
    testRunIds = [];
  }

  return {
    endpointId: filters.endpointId ?? '',
    behaviorIds: filters.behaviorIds ?? null,
    statusIds: filters.statusIds ?? null,
    timeRange,
    testRunIds,
    runFilterMode: testRunIds.length > 0 ? 'testRuns' : 'timeRange',
  };
}

export const INSIGHTS_TIME_RANGE_OPTIONS: {
  value: InsightsTimeRange;
  label: string;
}[] = [
  { value: 'always', label: 'Always' },
  { value: '1d', label: '1D' },
  { value: '7d', label: '7D' },
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
];

function toIsoDate(date: Date): string {
  return date.toISOString();
}

/** Map UI time-range pills to Insights date query parameters. */
export function timeRangeToStatsParams(
  timeRange: InsightsTimeRange
): Pick<
  import('@/utils/api-client/interfaces/insights').InsightsQuery,
  'months' | 'start_date' | 'end_date'
> {
  switch (timeRange) {
    case 'always':
      return {};
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
