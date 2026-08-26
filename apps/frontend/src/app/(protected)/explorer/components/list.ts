import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

const EXPLORER_FILTERS = {
  search: { kind: 'search', columns: ['name', 'description'] },
} as const;

/** Explorer sessions are TestSet rows flagged `explorer_row` -- same columns. */
export const explorerList = defineList({
  title: 'Explorer',
  resource: 'explorer sessions',
  capability: Capability.Explorer.READ,
  defaultPageSize: 25,
  filters: EXPLORER_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getExplorerClient().getExplorerTestSets(params),
  delete: {
    bulk: (factory: ApiClientFactory, ids: string[]) =>
      factory.getExplorerClient().bulkDeleteExplorerTestSets(ids),
    capability: Capability.Explorer.DELETE,
    capabilityMode: 'ambient',
    labelSingular: 'session',
    labelPlural: 'sessions',
    confirmMessage: count =>
      count === 1
        ? 'Are you sure you want to delete this session? Its tests and topics are deleted with it.'
        : `Are you sure you want to delete ${count} sessions? Their tests and topics are deleted with them.`,
  },
});
