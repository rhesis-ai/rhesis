import { gridSortToApiParams } from '@/utils/grid-sort';
import { buildListFilter } from './odata';
import {
  emptyFilters,
  type ListDescriptor,
  type ListParams,
  type ListState,
  type FilterSpecMap,
  type FiltersOf,
} from './define';

function isActive(value: string | string[] | undefined): boolean {
  return Array.isArray(value) ? value.length > 0 : Boolean(value);
}

/**
 * Active filters, not counting the search box -- the toolbar shows search
 * separately from the filter drawer's badge.
 */
export function countActiveFilters<S extends FilterSpecMap>(
  descriptor: ListDescriptor<unknown, S>,
  filters: FiltersOf<S>
): number {
  return Object.entries(descriptor.filters).filter(
    ([key, spec]) =>
      spec.kind !== 'search' &&
      isActive((filters as Record<string, string | string[]>)[key])
  ).length;
}

export function hasActiveFilters<S extends FilterSpecMap>(
  descriptor: ListDescriptor<unknown, S>,
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
export function listParams<T, S extends FilterSpecMap>(
  descriptor: ListDescriptor<T, S>,
  state: ListState<S>,
  extra: (string | undefined)[] = []
): ListParams {
  const $filter = buildListFilter(descriptor, state.filters, extra);
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

/**
 * The params for a descriptor's first page in its default state -- what a
 * server prefetch fetches, and what the client grid asks for on mount.
 */
export function firstPageParams<T, S extends FilterSpecMap>(
  descriptor: ListDescriptor<T, S>
): ListParams {
  return listParams(descriptor, {
    page: 1,
    pageSize: descriptor.defaultPageSize,
    sort: descriptor.defaultSort,
    filters: emptyFilters(descriptor),
  });
}
