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
  testSetId: { kind: 'raw' },
  endpointId: { kind: 'raw' },
  metric: { kind: 'raw' },
} as const;

export const annotationsList = defineList<
  Annotation,
  typeof ANNOTATIONS_FILTERS
>({
  title: 'Annotations',
  resource: 'annotations',
  capability: Capability.Annotation.READ,
  defaultPageSize: 25,
  // Newest judgement first: the hub is a worklist, not an archive.
  defaultSort: { by: 'updated_at', order: 'desc' },
  filters: ANNOTATIONS_FILTERS,
  delete: {
    // No bulk endpoint on annotations, so rows go one at a time.
    one: (factory: ApiClientFactory, id: string) =>
      factory.getAnnotationsClient().deleteAnnotation(id),
    capability: Capability.Annotation.DELETE,
    // Rows carry permitted_actions, and only the author may delete.
    capabilityMode: 'row',
    labelSingular: 'annotation',
    labelPlural: 'annotations',
    notSelectableReason: 'Only the author can delete this annotation',
  },
  extraParams: f => ({
    ...(f.search.trim() ? { search: f.search.trim() } : {}),
    ...(f.status === 'resolved' ? { resolved: true } : {}),
    ...(f.status === 'open' ? { resolved: false } : {}),
    ...(f.entityType ? { entity_type: f.entityType } : {}),
    ...(f.rating ? { rating: f.rating } : {}),
    ...(f.targetType ? { target_type: f.targetType } : {}),
    ...(f.testSetId ? { test_set_id: f.testSetId } : {}),
    ...(f.endpointId ? { endpoint_id: f.endpointId } : {}),
    ...(f.metric ? { metric: f.metric } : {}),
  }),
  list: (factory: ApiClientFactory, params) =>
    factory
      .getAnnotationsClient()
      .getAnnotations(params as AnnotationsQueryParams),
});
