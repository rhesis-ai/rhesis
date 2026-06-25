import {
  TraceQueryParams,
  type TraceMetricsStatus,
  type TraceSource,
  type TraceType,
} from '@/utils/api-client/interfaces/telemetry';

export type TraceTimeRange = 'all' | '24h' | '7d' | '30d' | 'custom';

export interface TraceDrawerFilters {
  projectId?: string;
  endpointId?: string;
  environment?: string;
  timeRange: TraceTimeRange;
  startTimeAfter?: string;
  startTimeBefore?: string;
  traceSource?: string;
  traceMetricsStatus?: string;
  testRunId?: string;
  testResultId?: string;
  testId?: string;
}

export const EMPTY_TRACE_DRAWER_FILTERS: TraceDrawerFilters = {
  timeRange: 'all',
};

export function countActiveTraceDrawerFilters(
  f: TraceDrawerFilters,
  options?: { excludeTestRunId?: boolean; testRunScope?: boolean }
): number {
  if (options?.testRunScope) {
    return [f.traceMetricsStatus, f.testResultId, f.testId].filter(Boolean)
      .length;
  }
  const filters = options?.excludeTestRunId
    ? { ...f, testRunId: undefined }
    : f;
  return [
    filters.projectId,
    filters.endpointId,
    filters.environment,
    filters.traceSource,
    filters.traceMetricsStatus,
    filters.testRunId,
    filters.testResultId,
    filters.testId,
    filters.startTimeBefore,
    (filters.timeRange !== 'all' && filters.timeRange !== 'custom') ||
    (filters.timeRange === 'custom' && filters.startTimeAfter)
      ? true
      : undefined,
  ].filter(Boolean).length;
}

export function hasActiveTraceDrawerFilters(
  f: TraceDrawerFilters,
  options?: { excludeTestRunId?: boolean; testRunScope?: boolean }
): boolean {
  if (options?.testRunScope) {
    return !!(f.traceMetricsStatus || f.testResultId || f.testId);
  }

  const filters = options?.excludeTestRunId
    ? { ...f, testRunId: undefined }
    : f;
  return !!(
    filters.projectId ||
    filters.endpointId ||
    filters.environment ||
    filters.traceSource ||
    filters.traceMetricsStatus ||
    filters.testRunId ||
    filters.testResultId ||
    filters.testId ||
    filters.startTimeBefore ||
    (filters.timeRange !== 'all' && filters.timeRange !== 'custom') ||
    (filters.timeRange === 'custom' && filters.startTimeAfter)
  );
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
    testResultId: filters.testResultId,
    testId: filters.testId,
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

export function buildTraceQueryParams(
  drawer: TraceDrawerFilters,
  searchQuery: string,
  typeFilter: string,
  limit: number,
  offset: number
): TraceQueryParams {
  const params: TraceQueryParams = { limit, offset };

  if (drawer.projectId) params.project_id = drawer.projectId;
  if (drawer.endpointId) params.endpoint_id = drawer.endpointId;
  if (drawer.environment) params.environment = drawer.environment;

  if (drawer.timeRange === 'custom') {
    if (drawer.startTimeAfter) params.start_time_after = drawer.startTimeAfter;
    if (drawer.startTimeBefore)
      params.start_time_before = drawer.startTimeBefore;
  } else if (drawer.timeRange !== 'all') {
    const after = timeRangeToStartTimeAfter(drawer.timeRange);
    if (after) params.start_time_after = after;
  }

  if (drawer.traceSource) {
    params.trace_source = drawer.traceSource as TraceSource;
  }
  if (drawer.traceMetricsStatus) {
    params.trace_metrics_status =
      drawer.traceMetricsStatus as TraceMetricsStatus;
  }
  if (drawer.testRunId) params.test_run_id = drawer.testRunId;
  if (drawer.testResultId) params.test_result_id = drawer.testResultId;
  if (drawer.testId) params.test_id = drawer.testId;

  if (searchQuery.trim()) params.search = searchQuery.trim();
  if (typeFilter && typeFilter !== 'all') {
    params.trace_type = typeFilter as TraceType;
  }

  return params;
}
