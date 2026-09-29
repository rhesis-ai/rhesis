import { TRACE_METRICS_STATUS } from '@/utils/api-client/interfaces/telemetry';
import {
  EMPTY_TRACE_DRAWER_FILTERS,
  type TraceDrawerFilters,
  type TraceTimeRange,
  type TraceView,
} from './trace-filter-params';

/**
 * The traces page keeps its view and drawer filters in the URL, so a reload or a
 * shared link shows the same table. Search text stays out: rewriting the URL on
 * every keystroke would flood the history.
 */

const VIEW_PARAM = 'view';

/** Filter field -> URL key. `project_id` keeps the name deep links already use. */
const SINGLE_KEYS = {
  projectId: 'project_id',
  endpointId: 'endpoint_id',
  environment: 'environment',
  startTimeAfter: 'start_time_after',
  startTimeBefore: 'start_time_before',
  traceSource: 'source',
  traceMetricsStatus: 'evaluation',
  testRunId: 'test_run_id',
  testResultId: 'test_result_id',
  testId: 'test_id',
  traceType: 'turns',
} as const satisfies Partial<Record<keyof TraceDrawerFilters, string>>;

const LIST_KEYS = {
  providers: 'provider',
  spanTypes: 'span_type',
  spanNames: 'span_name',
} as const satisfies Partial<Record<keyof TraceDrawerFilters, string>>;

const TIME_RANGE_PARAM = 'time';
const ROOT_PARAM = 'root';

const TIME_RANGES: TraceTimeRange[] = ['all', '24h', '7d', '30d', 'custom'];
const TRACE_SOURCES = ['test', 'operation'];
const TRACE_TYPES = ['Single-Turn', 'Multi-Turn'] as const;
const EVAL_STATUSES: string[] = Object.values(TRACE_METRICS_STATUS);

/** Every URL key this module owns, so writing filters clears stale ones first. */
const FILTER_PARAMS = [
  ...Object.values(SINGLE_KEYS),
  ...Object.values(LIST_KEYS),
  TIME_RANGE_PARAM,
  ROOT_PARAM,
];

export function viewFromSearchParams(params: URLSearchParams): TraceView {
  return params.get(VIEW_PARAM) === 'spans' ? 'spans' : 'traces';
}

/** Values that don't parse are dropped, so a hand-edited link can't break the page. */
export function filtersFromSearchParams(
  params: URLSearchParams
): TraceDrawerFilters {
  const filters: TraceDrawerFilters = { ...EMPTY_TRACE_DRAWER_FILTERS };
  const get = (key: string) => params.get(key) || undefined;

  filters.projectId = get(SINGLE_KEYS.projectId);
  filters.endpointId = get(SINGLE_KEYS.endpointId);
  filters.environment = get(SINGLE_KEYS.environment);
  filters.testRunId = get(SINGLE_KEYS.testRunId);
  filters.testResultId = get(SINGLE_KEYS.testResultId);
  filters.testId = get(SINGLE_KEYS.testId);

  const source = get(SINGLE_KEYS.traceSource);
  if (source && TRACE_SOURCES.includes(source)) filters.traceSource = source;

  const evaluation = get(SINGLE_KEYS.traceMetricsStatus);
  if (evaluation && EVAL_STATUSES.includes(evaluation)) {
    filters.traceMetricsStatus = evaluation;
  }

  const turns = TRACE_TYPES.find(t => t === get(SINGLE_KEYS.traceType));
  if (turns) filters.traceType = turns;

  const range = TIME_RANGES.find(r => r === get(TIME_RANGE_PARAM));
  if (range) filters.timeRange = range;
  if (filters.timeRange === 'custom') {
    filters.startTimeAfter = validIsoDate(get(SINGLE_KEYS.startTimeAfter));
    filters.startTimeBefore = validIsoDate(get(SINGLE_KEYS.startTimeBefore));
  }

  for (const [field, key] of Object.entries(LIST_KEYS) as [
    keyof typeof LIST_KEYS,
    string,
  ][]) {
    const values = params.getAll(key).filter(Boolean);
    if (values.length) filters[field] = values;
  }

  const root = params.get(ROOT_PARAM);
  if (root === 'true' || root === 'false') filters.isRoot = root === 'true';

  // Leave unset fields out, so the object compares equal to one built in the drawer.
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined)
  ) as TraceDrawerFilters;
}

/**
 * *current* with the view and filters replaced. Other params (`open_trace`,
 * `open_span`, ...) are kept.
 */
export function withTraceUrlState(
  current: URLSearchParams,
  view: TraceView,
  filters: TraceDrawerFilters
): URLSearchParams {
  const next = new URLSearchParams(current);
  [VIEW_PARAM, ...FILTER_PARAMS].forEach(key => next.delete(key));

  if (view === 'spans') next.set(VIEW_PARAM, 'spans');

  for (const [field, key] of Object.entries(SINGLE_KEYS) as [
    keyof typeof SINGLE_KEYS,
    string,
  ][]) {
    const value = filters[field];
    // Custom bounds only mean something with the custom range.
    const isBound = field === 'startTimeAfter' || field === 'startTimeBefore';
    if (value && (!isBound || filters.timeRange === 'custom')) {
      next.set(key, value);
    }
  }
  for (const [field, key] of Object.entries(LIST_KEYS) as [
    keyof typeof LIST_KEYS,
    string,
  ][]) {
    filters[field]?.forEach(value => next.append(key, value));
  }
  // The range token, not a timestamp, so a reload recomputes "last 24h" from now.
  if (filters.timeRange !== 'all')
    next.set(TIME_RANGE_PARAM, filters.timeRange);
  if (filters.isRoot !== undefined)
    next.set(ROOT_PARAM, String(filters.isRoot));

  return next;
}

/** True when the URL narrows the list, so a prefetched unfiltered page won't match. */
export function hasTraceUrlFilters(params: URLSearchParams): boolean {
  return FILTER_PARAMS.some(
    key => key !== SINGLE_KEYS.projectId && params.has(key)
  );
}

function validIsoDate(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? undefined : new Date(time).toISOString();
}
