import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

const ENDPOINTS_FILTERS = {
  search: {
    kind: 'search',
    columns: ['name', 'environment', 'connection_type', 'description'],
  },
  connectionType: { kind: 'enum', column: 'connection_type' },
  environment: { kind: 'enum', column: 'environment' },
  status: { kind: 'enum', column: 'status/name' },
} as const;

export const endpointsList = defineList({
  title: 'Endpoints',
  resource: 'endpoints',
  capability: Capability.Endpoint.READ,
  defaultPageSize: 10,
  filters: ENDPOINTS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getEndpointsClient().getEndpoints(params),
  delete: {
    bulk: (factory: ApiClientFactory, ids: string[]) =>
      factory.getEndpointsClient().bulkDeleteEndpoints(ids),
    capability: Capability.Endpoint.DELETE,
    capabilityMode: 'ambient',
    labelSingular: 'endpoint',
    labelPlural: 'endpoints',
    confirmMessage: count =>
      count === 1
        ? 'Are you sure you want to delete this endpoint? Related data will not be deleted.'
        : `Are you sure you want to delete ${count} endpoints? Related data will not be deleted.`,
  },
});
