import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

const EXPERIMENTS_FILTERS = {
  search: {
    kind: 'search',
    columns: ['name', 'description', 'visibility', 'project/name'],
  },
  visibility: { kind: 'enum', column: 'visibility' },
} as const;

/**
 * `listExperiments` predates the `PaginatedResponse<T>` shape every other
 * client method returns (flat `{data, totalCount}`, and `filter` instead of
 * `$filter`) -- adapted here rather than changing the client, since other
 * callers of `listExperiments` still expect its own shape.
 */
export const experimentsList = defineList({
  title: 'Experiments',
  resource: 'experiments',
  capability: Capability.Experiment.READ,
  defaultPageSize: 25,
  filters: EXPERIMENTS_FILTERS,
  list: async (factory: ApiClientFactory, params) => {
    const resp = await factory.getParametersClient().listExperiments({
      skip: params.skip,
      limit: params.limit,
      sort_by: params.sort_by,
      sort_order: params.sort_order,
      filter: params.$filter,
    });
    return {
      data: resp.data,
      pagination: {
        totalCount: resp.totalCount,
        skip: params.skip,
        limit: params.limit,
        currentPage: Math.floor(params.skip / params.limit) + 1,
        pageSize: params.limit,
        totalPages: Math.ceil(resp.totalCount / params.limit),
      },
    };
  },
});
