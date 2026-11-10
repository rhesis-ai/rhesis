import type { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Capability } from '@/constants/capabilities';
import { defineList } from '@/utils/list';

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** `column eq <id>` OR'd over the ids. Anything not a UUID is dropped. */
function anyIdClause(column: string, values: string[]): string | undefined {
  const ids = values.filter(v => UUID_PATTERN.test(v));
  if (ids.length === 0) return undefined;
  const clauses = ids.map(id => `${column} eq ${id}`);
  return clauses.length === 1 ? clauses[0] : `(${clauses.join(' or ')})`;
}

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
  impactIds: {
    kind: 'raw',
    multi: true,
    toOData: (value: string[]) => anyIdClause('impact_id', value),
  },
  // 'top_level', 'has_parent', or one parent's id. Anything else: no clause.
  hierarchy: {
    kind: 'raw',
    toOData: (value: string) => {
      if (value === 'top_level') return 'parent_id eq null';
      if (value === 'has_parent') return 'parent_id ne null';
      return anyIdClause('parent_id', [value]);
    },
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
