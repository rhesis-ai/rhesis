import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { SpanSummary } from '@/utils/api-client/interfaces/telemetry';
import { Capability } from '@/constants/capabilities';
import { defineList, type FiltersOf } from '@/utils/list';
import {
  buildSpanQueryParams,
  type TraceDrawerFilters,
} from './trace-filter-params';

/** Same shape as the traces list: plain REST params, mapped in `extraParams`. */
const SPANS_FILTERS = {
  search: { kind: 'raw' },
  projectId: { kind: 'raw' },
  environment: { kind: 'raw' },
  timeRange: { kind: 'raw' },
  startTimeAfter: { kind: 'raw' },
  startTimeBefore: { kind: 'raw' },
  traceSource: { kind: 'raw' },
  providers: { kind: 'raw', multi: true },
  testRunId: { kind: 'raw' },
  testResultId: { kind: 'raw' },
  testId: { kind: 'raw' },
  traceType: { kind: 'raw' },
  spanTypes: { kind: 'raw', multi: true },
  spanNames: { kind: 'raw', multi: true },
  /** 'true', 'false', or '' for both -- list filters are strings. */
  isRoot: { kind: 'raw' },
} as const;

export type SpansListFilters = FiltersOf<typeof SPANS_FILTERS>;

/** The list's string filters for *drawer* and *search*. */
export function spansListFilters(
  drawer: TraceDrawerFilters,
  search: string
): SpansListFilters {
  return {
    search,
    projectId: drawer.projectId ?? '',
    environment: drawer.environment ?? '',
    timeRange: drawer.timeRange,
    startTimeAfter: drawer.startTimeAfter ?? '',
    startTimeBefore: drawer.startTimeBefore ?? '',
    traceSource: drawer.traceSource ?? '',
    providers: drawer.providers ?? [],
    testRunId: drawer.testRunId ?? '',
    testResultId: drawer.testResultId ?? '',
    testId: drawer.testId ?? '',
    traceType: drawer.traceType ?? '',
    spanTypes: drawer.spanTypes ?? [],
    spanNames: drawer.spanNames ?? [],
    isRoot: drawer.isRoot === undefined ? '' : String(drawer.isRoot),
  };
}

function toDrawerFilters(f: SpansListFilters): TraceDrawerFilters {
  return {
    projectId: f.projectId || undefined,
    environment: f.environment || undefined,
    timeRange: (f.timeRange || 'all') as TraceDrawerFilters['timeRange'],
    startTimeAfter: f.startTimeAfter || undefined,
    startTimeBefore: f.startTimeBefore || undefined,
    traceSource: f.traceSource || undefined,
    providers: f.providers,
    testRunId: f.testRunId || undefined,
    testResultId: f.testResultId || undefined,
    testId: f.testId || undefined,
    traceType: (f.traceType || undefined) as TraceDrawerFilters['traceType'],
    spanTypes: f.spanTypes,
    spanNames: f.spanNames,
    isRoot: f.isRoot === '' ? undefined : f.isRoot === 'true',
  };
}

/**
 * Spans are project-scoped like traces: the active project's `X-Project-Id` goes
 * on the client, and its id is sent as `project_id` unless the drawer overrides it.
 */
export function spansList(scopedProjectId: string | null) {
  return defineList<SpanSummary, typeof SPANS_FILTERS>({
    title: 'Spans',
    resource: 'spans',
    capability: Capability.Telemetry.READ,
    defaultPageSize: 50,
    defaultSort: { by: 'start_time', order: 'desc' },
    filters: SPANS_FILTERS,
    extraParams: f => {
      const params = buildSpanQueryParams(toDrawerFilters(f), f.search);
      if (scopedProjectId && !f.projectId) {
        params.project_id = scopedProjectId;
      }
      return { ...params };
    },
    list: async (_factory, params) => {
      const { skip, limit, sort_by, sort_order, ...rest } = params;
      const response = await new ApiClientFactory(
        undefined,
        scopedProjectId ?? undefined
      )
        .getTelemetryClient()
        .listSpans({
          ...rest,
          limit,
          offset: skip,
          sort_by,
          sort_order: sort_order as 'asc' | 'desc' | undefined,
        });
      return {
        data: response.spans,
        pagination: {
          totalCount: response.total,
          skip,
          limit,
          currentPage: Math.floor(skip / limit) + 1,
          pageSize: limit,
          totalPages: Math.ceil(response.total / limit),
        },
      };
    },
  });
}
