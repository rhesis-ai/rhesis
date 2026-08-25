import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { escapeODataValue } from '@/utils/odata-filter';
import { defineDirectory, type FiltersOf } from '@/utils/directory';

/** Tag applied to OWASP metrics by the tag_owasp_metrics_and_behaviors migration. */
export const OWASP_METRIC_TAG_NAME = 'OWASP';
/**
 * Pseudo-backend pill value for the OWASP tag -- no metric actually has this
 * as its `backend_type`, so it's mapped to a tag-based OData clause instead
 * of the usual `backend_type/type_value eq ...` comparison.
 */
export const OWASP_METRIC_FILTER_VALUE = 'owasp';

/**
 * OData $select expression for the metrics directory list -- trims the
 * response to only the fields the grid/filters render. Shared between the
 * server component (initial page fetch) and the client component
 * (subsequent pagination/filter fetches) so both request the same shape.
 */
export const METRICS_SELECT =
  'name,description,score_type,metric_scope,metric_type,backend_type,requirements,tags';

const METRICS_FILTERS = {
  search: { kind: 'search', columns: ['name', 'description'] },
  // `tolower` only on the left -- kept asymmetric to match the backend
  // column's actual casing instead of the usual case-insensitive compare.
  backend: {
    kind: 'raw',
    multi: true,
    toOData: (value: string[]) => {
      const values = value.filter(Boolean);
      if (values.length === 0) return undefined;
      const clauses = values.map(b =>
        b === OWASP_METRIC_FILTER_VALUE
          ? `_tags_relationship/any(x: tolower(x/tag/name) eq tolower('${escapeODataValue(OWASP_METRIC_TAG_NAME)}'))`
          : `tolower(backend_type/type_value) eq '${escapeODataValue(b)}'`
      );
      return clauses.length === 1 ? clauses[0] : `(${clauses.join(' or ')})`;
    },
  },
  type: { kind: 'multiEnum', column: 'metric_type/type_value' },
  scoreType: { kind: 'multiEnum', column: 'score_type' },
  requirement: { kind: 'navAny', nav: 'requirements', column: 'x/name' },
  // Not an OData clause -- filters a Postgres JSONB array via a dedicated
  // query param instead, see `extraParams` below.
  metricScope: { kind: 'raw', multi: true },
} as const;

export const metricsDirectory = defineDirectory({
  title: 'Metrics',
  resource: 'metrics',
  capability: Capability.Metric.READ,
  defaultPageSize: 25,
  defaultSort: { by: 'name', order: 'asc' },
  filters: METRICS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getMetricsClient().getMetrics(params),
  extraParams: (filters: FiltersOf<typeof METRICS_FILTERS>) => ({
    $select: METRICS_SELECT,
    ...(filters.metricScope.length > 0
      ? { metric_scope: filters.metricScope.join(',') }
      : {}),
  }),
});
