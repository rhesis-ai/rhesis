/**
 * OData $select expression for the metrics directory list -- trims the
 * response to only the fields the grid/filters render. Shared between the
 * server component (initial page fetch) and the client component
 * (subsequent pagination/filter fetches) so both request the same shape.
 */
export const METRICS_SELECT =
  'name,description,score_type,metric_scope,metric_type,backend_type,behaviors';

/** Default page size for the metrics directory grid. */
export const DEFAULT_METRICS_PAGE_SIZE = 25;
