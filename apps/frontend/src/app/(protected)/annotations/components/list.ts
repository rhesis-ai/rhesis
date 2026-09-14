import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  Annotation,
  AnnotationsQueryParams,
} from '@/utils/api-client/interfaces/annotation';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

/**
 * All filters are plain REST query params, not OData -- the annotations
 * endpoint takes `entity_type`/`search`/`resolved`/... directly, so every spec
 * is a bare `raw` (contributes no `$filter` clause) and the mapping lives in
 * `extraParams`.
 */
const ANNOTATIONS_FILTERS = {
  search: { kind: 'raw' },
  /** Pill value: '' (all), 'open', or 'resolved' -- mapped to the boolean `resolved` param. */
  status: { kind: 'raw' },
  entityType: { kind: 'raw' },
  rating: { kind: 'raw' },
  targetType: { kind: 'raw' },
} as const;

export const annotationsList = defineList<
  Annotation,
  typeof ANNOTATIONS_FILTERS
>({
  title: 'Annotations',
  resource: 'annotations',
  capability: Capability.Annotation.READ,
  defaultPageSize: 25,
  filters: ANNOTATIONS_FILTERS,
  extraParams: f => ({
    ...(f.search.trim() ? { search: f.search.trim() } : {}),
    ...(f.status === 'resolved' ? { resolved: true } : {}),
    ...(f.status === 'open' ? { resolved: false } : {}),
    ...(f.entityType ? { entity_type: f.entityType } : {}),
    ...(f.rating ? { rating: f.rating } : {}),
    ...(f.targetType ? { target_type: f.targetType } : {}),
  }),
  list: (factory: ApiClientFactory, params) =>
    factory
      .getAnnotationsClient()
      .getAnnotations(params as AnnotationsQueryParams),
});
