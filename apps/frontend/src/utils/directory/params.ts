import { gridSortToApiParams } from '@/utils/grid-sort';
import { buildDirectoryFilter } from './odata';
import type {
  DirectoryDescriptor,
  DirectoryListParams,
  DirectoryState,
  FilterSpecMap,
  FiltersOf,
} from './define';

function isActive(value: string | string[] | undefined): boolean {
  return Array.isArray(value) ? value.length > 0 : Boolean(value);
}

/**
 * Active filters, not counting the search box -- the toolbar shows search
 * separately from the filter drawer's badge.
 */
export function countActiveFilters<S extends FilterSpecMap>(
  descriptor: DirectoryDescriptor<unknown, S>,
  filters: FiltersOf<S>
): number {
  return Object.entries(descriptor.filters).filter(
    ([key, spec]) =>
      spec.kind !== 'search' &&
      isActive((filters as Record<string, string | string[]>)[key])
  ).length;
}

export function hasActiveFilters<S extends FilterSpecMap>(
  descriptor: DirectoryDescriptor<unknown, S>,
  filters: FiltersOf<S>
): boolean {
  return countActiveFilters(descriptor, filters) > 0;
}

/**
 * The API list params for a given state: the `skip`/`limit`/`sort_by`/
 * `sort_order`/`$filter` block every list page used to spell out by hand.
 *
 * `extra` adds OData clauses the caller doesn't own, e.g. scoping an embedded
 * grid to one project.
 */
export function directoryListParams<T, S extends FilterSpecMap>(
  descriptor: DirectoryDescriptor<T, S>,
  state: DirectoryState<S>,
  extra: (string | undefined)[] = []
): DirectoryListParams {
  const $filter = buildDirectoryFilter(descriptor, state.filters, extra);
  // Grid column ids don't always match API sort fields (`tags` -> `tags_count`).
  const { sort_by, sort_order } = gridSortToApiParams([
    { field: state.sort.by, sort: state.sort.order },
  ]);

  return {
    skip: (state.page - 1) * state.pageSize,
    limit: state.pageSize,
    sort_by,
    sort_order,
    ...(descriptor.extraParams?.(state.filters) ?? {}),
    ...($filter ? { $filter } : {}),
  };
}
