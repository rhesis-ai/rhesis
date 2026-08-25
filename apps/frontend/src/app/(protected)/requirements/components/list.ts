import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

const REQUIREMENTS_FILTERS = {
  search: {
    kind: 'search',
    columns: ['name', 'description'],
    navs: [
      { nav: 'metrics', columns: ['name', 'description'] },
      { nav: '_tags_relationship', columns: ['tag/name'] },
    ],
  },
  // Not `enum`: 'all' (and anything else unrecognized) contributes no clause,
  // same as no filter at all -- there's no backend column for "either state".
  metricCount: {
    kind: 'raw',
    toOData: (value: string) => {
      if (value === 'has_metrics') return 'metrics/any()';
      if (value === 'no_metrics') return 'not metrics/any()';
      return undefined;
    },
  },
  tagNames: {
    kind: 'navAny',
    nav: '_tags_relationship',
    column: 'x/tag/name',
    multi: true,
  },
} as const;

export const requirementsList = defineList({
  title: 'Requirements',
  resource: 'requirements',
  capability: Capability.Requirement.READ,
  defaultPageSize: 25,
  defaultSort: { by: 'name', order: 'asc' },
  filters: REQUIREMENTS_FILTERS,
  list: (factory: ApiClientFactory, params) =>
    factory.getRequirementClient().getRequirementsPage(params),
});
