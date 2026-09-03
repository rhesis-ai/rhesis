import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { TraceSummary } from '@/utils/api-client/interfaces/telemetry';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';
import {
  buildTraceQueryParams,
  type TraceDrawerFilters,
} from './trace-filter-params';

/**
 * Every filter is a plain REST query param (the telemetry API takes no
 * OData), so all specs are bare `raw` and the mapping lives in `extraParams`
 * via the existing `buildTraceQueryParams`.
 */
const TRACES_FILTERS = {
  search: { kind: 'raw' },
  /** Pill value: 'all' or a TraceType. */
  typeFilter: { kind: 'raw' },
  projectId: { kind: 'raw' },
  endpointId: { kind: 'raw' },
  environment: { kind: 'raw' },
  timeRange: { kind: 'raw' },
  startTimeAfter: { kind: 'raw' },
  startTimeBefore: { kind: 'raw' },
  traceSource: { kind: 'raw' },
  traceMetricsStatus: { kind: 'raw' },
  testRunId: { kind: 'raw' },
  testResultId: { kind: 'raw' },
  testId: { kind: 'raw' },
} as const;

/**
 * Traces are project-scoped (fail-closed): the `list` factory param is
 * ignored in favor of one carrying the active project's `X-Project-Id`, and
 * the scope is also passed as `project_id` unless the drawer explicitly
 * overrides it. A factory function rather than a constant because the project
 * id is client state (`useActiveProject`), resolved per render. The server
 * prefetch passes its own `factory` (token + project header already set).
 */
export function tracesList(
  scopedProjectId: string | null,
  factory?: ApiClientFactory
) {
  return defineList<TraceSummary, typeof TRACES_FILTERS>({
    title: 'Traces',
    resource: 'traces',
    capability: Capability.Telemetry.READ,
    defaultPageSize: 50,
    filters: TRACES_FILTERS,
    extraParams: f => {
      const { search, typeFilter, ...drawer } = f;
      const params = buildTraceQueryParams(
        drawer as unknown as TraceDrawerFilters,
        search,
        typeFilter
      );
      if (scopedProjectId && !drawer.projectId) {
        params.project_id = scopedProjectId;
      }
      return params;
    },
    list: async (_factory, params) => {
      const {
        skip,
        limit,
        sort_by: _sortBy,
        sort_order: _sortOrder,
        ...rest
      } = params;
      const response = await (
        factory ?? new ApiClientFactory(undefined, scopedProjectId ?? undefined)
      )
        .getTelemetryClient()
        .listTraces({ ...rest, limit, offset: skip });
      return {
        data: response.traces,
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
