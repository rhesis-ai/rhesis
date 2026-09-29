import type {
  SpanFilterParams,
  TraceMetricsStatus,
  TraceQueryParams,
  TraceSource,
  TraceType,
} from '@/utils/api-client/interfaces/telemetry';

export type TraceTimeRange = 'all' | '24h' | '7d' | '30d' | 'custom';

/** Which table the traces page shows: one row per trace, or one per span. */
export type TraceView = 'traces' | 'spans';

export interface TraceDrawerFilters {
  projectId?: string;
  endpointId?: string;
  environment?: string;
  timeRange: TraceTimeRange;
  startTimeAfter?: string;
  startTimeBefore?: string;
  traceSource?: string;
  traceMetricsStatus?: string;
  /** Several at once: a trace matches if any of its priced calls used one of them. */
  providers?: string[];
  testRunId?: string;
  testResultId?: string;
  testId?: string;
  /** Unset means both; 'all' is never stored here. */
  traceType?: Exclude<TraceType, 'all'>;
  // Spans view only. Kept while the traces view shows, so switching back restores them.
  spanTypes?: string[];
  spanNames?: string[];
  /** true: root spans only; false: child spans only; unset: both. */
  isRoot?: boolean;
}

export const EMPTY_TRACE_DRAWER_FILTERS: TraceDrawerFilters = {
  timeRange: 'all',
};

interface ActiveFilterOptions {
  excludeTestRunId?: boolean;
  testRunScope?: boolean;
  /** Only filters the shown table applies are counted. Defaults to 'traces'. */
  view?: TraceView;
}

/** One flag per drawer section, so the badge counts sections, not values. */
function activeFilterFlags(
  f: TraceDrawerFilters,
  options?: ActiveFilterOptions
): boolean[] {
  const spans = options?.view === 'spans';
  // The spans endpoint has no endpoint or evaluation filter, and the traces one
  // has no span filters, so each view ignores the other's.
  const viewOnly = spans
    ? [!!f.spanTypes?.length, !!f.spanNames?.length, f.isRoot !== undefined]
    : [!!f.traceMetricsStatus];

  if (options?.testRunScope) {
    return [...viewOnly, !!f.providers?.length, !!f.testResultId, !!f.testId];
  }

  const testRunId = options?.excludeTestRunId ? undefined : f.testRunId;
  return [
    ...viewOnly,
    !!f.projectId,
    !spans && !!f.endpointId,
    !!f.environment,
    !!f.traceSource,
    !!f.traceType,
    !!f.providers?.length,
    !!testRunId,
    !!f.testResultId,
    !!f.testId,
    !!f.startTimeBefore,
    (f.timeRange !== 'all' && f.timeRange !== 'custom') ||
      (f.timeRange === 'custom' && !!f.startTimeAfter),
  ];
}

export function countActiveTraceDrawerFilters(
  f: TraceDrawerFilters,
  options?: ActiveFilterOptions
): number {
  return activeFilterFlags(f, options).filter(Boolean).length;
}

export function hasActiveTraceDrawerFilters(
  f: TraceDrawerFilters,
  options?: ActiveFilterOptions
): boolean {
  return activeFilterFlags(f, options).some(Boolean);
}

/** Keep only filters meaningful when traces are scoped to a single test run. */
export function sanitizeTraceDrawerFiltersForTestRunScope(
  filters: TraceDrawerFilters,
  testRunId: string
): TraceDrawerFilters {
  return {
    timeRange: 'all',
    testRunId,
    traceMetricsStatus: filters.traceMetricsStatus,
    // Kept: one run can span several providers, so narrowing to one is still useful.
    providers: filters.providers,
    testResultId: filters.testResultId,
    testId: filters.testId,
    spanTypes: filters.spanTypes,
    spanNames: filters.spanNames,
    isRoot: filters.isRoot,
  };
}

export function timeRangeToStartTimeAfter(
  range: TraceTimeRange
): string | undefined {
  const now = Date.now();
  switch (range) {
    case '24h':
      return new Date(now - 24 * 60 * 60 * 1000).toISOString();
    case '7d':
      return new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();
    case '30d':
      return new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();
    default:
      return undefined;
  }
}

export function inferTimeRange(
  startTimeAfter?: string,
  startTimeBefore?: string
): TraceTimeRange {
  if (startTimeBefore) return 'custom';
  if (!startTimeAfter) return 'all';

  const filterTime = new Date(startTimeAfter).getTime();
  const diff = Date.now() - filterTime;
  const hour24 = 24 * 60 * 60 * 1000;
  const day7 = 7 * 24 * 60 * 60 * 1000;
  const day30 = 30 * 24 * 60 * 60 * 1000;

  if (Math.abs(diff - hour24) < hour24 * 0.05) return '24h';
  if (Math.abs(diff - day7) < day7 * 0.05) return '7d';
  if (Math.abs(diff - day30) < day30 * 0.05) return '30d';

  return 'custom';
}

function timeRangeParams(
  drawer: TraceDrawerFilters
): Pick<TraceQueryParams, 'start_time_after' | 'start_time_before'> {
  if (drawer.timeRange === 'custom') {
    return {
      ...(drawer.startTimeAfter
        ? { start_time_after: drawer.startTimeAfter }
        : {}),
      ...(drawer.startTimeBefore
        ? { start_time_before: drawer.startTimeBefore }
        : {}),
    };
  }
  const after = timeRangeToStartTimeAfter(drawer.timeRange);
  return after ? { start_time_after: after } : {};
}

/** Filter params only -- pagination (`limit`/`offset`) is the list hook's job. */
export function buildTraceQueryParams(
  drawer: TraceDrawerFilters,
  searchQuery: string
): Omit<TraceQueryParams, 'limit' | 'offset'> {
  const params: Omit<TraceQueryParams, 'limit' | 'offset'> = {
    ...timeRangeParams(drawer),
  };

  if (drawer.projectId) params.project_id = drawer.projectId;
  if (drawer.endpointId) params.endpoint_id = drawer.endpointId;
  if (drawer.environment) params.environment = drawer.environment;
  if (drawer.traceSource) {
    params.trace_source = drawer.traceSource as TraceSource;
  }
  if (drawer.traceMetricsStatus) {
    params.trace_metrics_status =
      drawer.traceMetricsStatus as TraceMetricsStatus;
  }
  if (drawer.providers?.length) params.provider = drawer.providers;
  if (drawer.testRunId) params.test_run_id = drawer.testRunId;
  if (drawer.testResultId) params.test_result_id = drawer.testResultId;
  if (drawer.testId) params.test_id = drawer.testId;
  if (drawer.traceType) params.trace_type = drawer.traceType;

  if (searchQuery.trim()) params.search = searchQuery.trim();

  return params;
}

/** Spans-list filter params. Endpoint and evaluation have no spans equivalent. */
export function buildSpanQueryParams(
  drawer: TraceDrawerFilters,
  searchQuery: string
): SpanFilterParams {
  const params: SpanFilterParams = { ...timeRangeParams(drawer) };

  if (drawer.projectId) params.project_id = drawer.projectId;
  if (drawer.environment) params.environment = drawer.environment;
  if (drawer.traceSource) {
    params.trace_source = drawer.traceSource as TraceSource;
  }
  if (drawer.providers?.length) params.provider = drawer.providers;
  if (drawer.testRunId) params.test_run_id = drawer.testRunId;
  if (drawer.testResultId) params.test_result_id = drawer.testResultId;
  if (drawer.testId) params.test_id = drawer.testId;
  if (drawer.traceType) params.trace_type = drawer.traceType;
  if (drawer.spanTypes?.length) params.span_type = drawer.spanTypes;
  if (drawer.spanNames?.length) params.span_name = drawer.spanNames;
  if (drawer.isRoot !== undefined) params.is_root = drawer.isRoot;

  if (searchQuery.trim()) params.search = searchQuery.trim();

  return params;
}
