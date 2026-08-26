'use client';

import * as React from 'react';
import type { GridPaginationModel, GridSortModel } from '@mui/x-data-grid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  listParams,
  type ListDescriptor,
  type ListSort,
  type FilterSpecMap,
  type FiltersOf,
} from '@/utils/list';
import { useListAuthGate } from './useListAuthGate';
import { usePaginatedList } from './usePaginatedList';

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
  }: UseListOptions<T, S>
) {
  const gate = useListAuthGate(descriptor);

  const [sortModel, setSortModel] = React.useState<GridSortModel>([
    { field: descriptor.defaultSort.by, sort: descriptor.defaultSort.order },
  ]);
  // An un-sorted grid (user cleared the column sort) falls back to the default.
  const sort: ListSort = {
    by: sortModel[0]?.field ?? descriptor.defaultSort.by,
    order: sortModel[0]?.sort ?? descriptor.defaultSort.order,
  };

  const list = usePaginatedList<T>({
    fetchPage: ({ skip, limit }) =>
      descriptor.list(
        new ApiClientFactory(),
        listParams(
          descriptor,
          {
            page: skip / limit + 1,
            pageSize: limit,
            sort,
            filters,
          },
          extraFilters ?? []
        )
      ),
    filterFingerprint: JSON.stringify({ filters, sort, extraFilters }),
    defaultPageSize: descriptor.defaultPageSize,
    initialData,
    initialTotalCount,
    onData,
    onError,
    enabled: gate.ready && enabled,
  });

  return {
    ...list,
    ready: gate.ready,
    gateNode: gate.ready ? null : gate.node,
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
    onSortModelChange: setSortModel,
  };
}
