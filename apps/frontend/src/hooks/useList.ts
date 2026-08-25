'use client';

import type { GridPaginationModel } from '@mui/x-data-grid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  listParams,
  type ListDescriptor,
  type FilterSpecMap,
  type FiltersOf,
} from '@/utils/list';
import { useListAuthGate } from './useListAuthGate';
import { usePaginatedList } from './usePaginatedList';

interface UseListOptions<T, S extends FilterSpecMap> {
  filters: FiltersOf<S>;
  initialData?: T[];
  initialTotalCount?: number;
  onData?: (data: T[]) => void;
  onError?: (error: unknown) => void;
}

/**
 * The client-side half of a list page: permission gate + paginated fetch,
 * both driven off one descriptor. Page/rowsPerPage state lives in
 * `usePaginatedList`; filters are owned by the caller and passed in.
 */
export function useList<T, S extends FilterSpecMap>(
  descriptor: ListDescriptor<T, S>,
  {
    filters,
    initialData,
    initialTotalCount,
    onData,
    onError,
  }: UseListOptions<T, S>
) {
  const gate = useListAuthGate(descriptor);

  const list = usePaginatedList<T>({
    fetchPage: ({ skip, limit }) =>
      descriptor.list(
        new ApiClientFactory(),
        listParams(descriptor, {
          page: skip / limit + 1,
          pageSize: limit,
          sort: descriptor.defaultSort,
          filters,
        })
      ),
    filterFingerprint: JSON.stringify(filters),
    defaultPageSize: descriptor.defaultPageSize,
    initialData,
    initialTotalCount,
    onData,
    onError,
    enabled: gate.ready,
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
  };
}
