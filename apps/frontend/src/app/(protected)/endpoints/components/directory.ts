import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineDirectory } from '@/utils/directory';

const ENDPOINTS_FILTERS = {
  search: {
    kind: 'search',
    columns: ['name', 'environment', 'connection_type', 'description'],
  },
  connectionType: { kind: 'enum', column: 'connection_type' },
  environment: { kind: 'enum', column: 'environment' },
  status: { kind: 'enum', column: 'status/name' },
} as const;

export const endpointsDirectory = defineDirectory({
  title: 'Endpoints',
  resource: 'endpoints',
  capability: Capability.Endpoint.READ,
  defaultPageSize: 10,
  filters: ENDPOINTS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getEndpointsClient().getEndpoints(params),
});
