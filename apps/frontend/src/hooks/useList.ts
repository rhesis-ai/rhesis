'use client';

import * as React from 'react';
import type {
  GridCallbackDetails,
  GridPaginationModel,
  GridSortModel,
} from '@mui/x-data-grid';
import { useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { readActiveProjectId } from '@/utils/active-project';
import { useSkeletonMode } from '@/components/loading/SkeletonMode';
import {
  descriptorId,
  firstPageParams,
  listParams,
  readFirstPage,
  writeFirstPage,
  type ListCacheScope,
  type ListDescriptor,
  type ListSort,
  type FilterSpecMap,
  type FiltersOf,
  type CachedFirstPage,
} from '@/utils/list';
import { useListAuthGate } from './useListAuthGate';
import { usePaginatedList } from './usePaginatedList';

/**
 * The grid clears its sort on the third header click, but a list always keeps
 * one. Clearing the default column flips it: re-applying the default there
 * would be a no-op, so a list that starts on `start_time desc` could never
 * reach asc.
 *
 * The grid also clears a sort whose field isn't one of its columns (e.g. a
 * `created_at` default with no Created column), on mount and whenever columns
 * change. That isn't a click, so the current sort is kept.
 */
export function nextSortModel(
  prev: GridSortModel,
  model: GridSortModel,
  defaultSort: ListSort,
  isColumn: (field: string) => boolean = () => true
): GridSortModel {
  if (model.length > 0) return model;
  const current = prev[0];
  if (current && !isColumn(current.field)) return prev;
  if (current?.field === defaultSort.by && current.sort) {
    return [
      { field: current.field, sort: current.sort === 'asc' ? 'desc' : 'asc' },
    ];
  }
  return [{ field: defaultSort.by, sort: defaultSort.order }];
}

interface UseListOptions<T, S extends FilterSpecMap> {
  filters: FiltersOf<S>;
  /**
   * OData clauses the caller doesn't own, passed through to `listParams` --
   * e.g. scoping an embedded grid to one project, or Tests' resolved
   * Insights id filter.
   */
  extraFilters?: (string | undefined)[];
  /**
   * Extra fetch gate AND'd with the auth gate -- e.g. Tests waiting for its
   * Insights deep-link filter to resolve. Defaults to `true`.
   */
  enabled?: boolean;
  initialData?: T[];
  initialTotalCount?: number;
  onData?: (data: T[]) => void;
  onError?: (error: unknown) => void;
  /** Live polling -- see `usePaginatedList`. */
  pollMs?: (data: T[]) => number | false;
}

/**
 * The client-side half of a list page: permission gate + paginated fetch +
 * sort state, all driven off one descriptor. Page/rowsPerPage state lives in
 * `usePaginatedList`; sort starts from `descriptor.defaultSort` (so it always
 * matches what an SSR prefetch used); filters are owned by the caller and
 * passed in.
 */
export function useList<T, S extends FilterSpecMap>(
  descriptor: ListDescriptor<T, S>,
  {
    filters,
    extraFilters,
    enabled = true,
    initialData,
    initialTotalCount,
    onData,
    onError,
    pollMs,
  }: UseListOptions<T, S>
) {
  const gate = useListAuthGate(descriptor);

  const [sortModel, setSortModel] = React.useState<GridSortModel>([
    { field: descriptor.defaultSort.by, sort: descriptor.defaultSort.order },
  ]);
  const sort: ListSort = {
    by: sortModel[0]?.field ?? descriptor.defaultSort.by,
    order: sortModel[0]?.sort ?? descriptor.defaultSort.order,
  };

  // The first page in its default state is what a return visit's loading view
  // draws from the cache, so only that page is kept.
  const queryClient = useQueryClient();
  const cacheScope = useListCacheScope();
  const skeleton = useSkeletonMode();
  const firstPage = React.useMemo(
    () => JSON.stringify(firstPageParams(descriptor)),
    [descriptor]
  );
  const paramsFor = (page: number, pageSize: number) =>
    listParams(
      descriptor,
      { page, pageSize, sort, filters },
      extraFilters ?? []
    );
  const remember = (
    scope: ListCacheScope | null,
    params: object,
    page: CachedFirstPage<T>
  ) => {
    if (scope && JSON.stringify(params) === firstPage) {
      writeFirstPage(queryClient, descriptor, scope, page);
    }
  };

  // Read once, on mount: a loading view never fetches, so this is all it shows.
  const [cached] = React.useState(() => {
    const scope = cacheScope();
    if (!skeleton || initialData !== undefined || !scope) return undefined;
    const params = paramsFor(1, descriptor.defaultPageSize);
    return JSON.stringify(params) === firstPage
      ? readFirstPage<T>(queryClient, descriptor, scope)
      : undefined;
  });

  // The server's first page, which the client doesn't fetch again.
  React.useEffect(() => {
    if (initialData === undefined || skeleton) return;
    remember(cacheScope(), paramsFor(1, descriptor.defaultPageSize), {
      data: initialData,
      totalCount: initialTotalCount ?? 0,
    });
    // Once, for what the page arrived with.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const list = usePaginatedList<T>({
    fetchPage: async ({ skip, limit }) => {
      const params = paramsFor(skip / limit + 1, limit);
      // Taken before the request, so a project switch mid-flight can't file
      // this page under the new project.
      const scope = cacheScope();
      const response = await descriptor.list(new ApiClientFactory(), params);
      remember(scope, params, {
        data: response.data,
        totalCount: response.pagination.totalCount,
      });
      return response;
    },
    filterFingerprint: JSON.stringify({
      descriptor: descriptorId(descriptor),
      filters,
      sort,
      extraFilters,
    }),
    defaultPageSize: descriptor.defaultPageSize,
    initialData: initialData ?? cached?.data,
    initialTotalCount: initialData ? initialTotalCount : cached?.totalCount,
    onData,
    onError,
    pollMs,
    enabled: gate.ready && enabled,
  });

  return {
    ...list,
    ready: gate.ready,
    gateNode: gate.ready ? null : gate.node,
    /** A loading view drawing the rows of an earlier visit, not placeholders. */
    fromCache: cached !== undefined,
    /** Spread onto `<BaseDataGrid>` alongside `rowCount`/`loading`/`serverSidePagination`. */
    paginationModel: { page: list.page, pageSize: list.rowsPerPage },
    onPaginationModelChange: (model: GridPaginationModel) => {
      if (model.pageSize !== list.rowsPerPage) {
        list.onRowsPerPageChange(model.pageSize);
      } else {
        list.onPageChange(model.page);
      }
    },
    /** Spread onto a sortable `<BaseDataGrid>`; omit for grids with fixed sort. */
    sortModel,
    onSortModelChange: (model: GridSortModel, details?: GridCallbackDetails) =>
      setSortModel(prev =>
        nextSortModel(
          prev,
          model,
          descriptor.defaultSort,
          details && (field => details.api.getColumn(field) !== undefined)
        )
      ),
  };
}

/**
 * The scope a cached list page belongs to, or null while the session doesn't
 * name a user and an organization yet. A function, so the project is read
 * from its cookie when the page is fetched, as the API client reads it.
 */
function useListCacheScope(): () => ListCacheScope | null {
  const { data: session } = useSession();
  const userId = session?.user?.id;
  const organizationId = session?.user?.organization_id;
  return () =>
    userId && organizationId
      ? { userId, organizationId, projectId: readActiveProjectId() ?? '' }
      : null;
}
