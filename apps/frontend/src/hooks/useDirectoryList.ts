'use client';

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  directoryListParams,
  type DirectoryDescriptor,
  type FilterSpecMap,
  type FiltersOf,
} from '@/utils/directory';
import { useDirectoryAuthGate } from './useDirectoryAuthGate';
import { usePaginatedList } from './usePaginatedList';

interface UseDirectoryListOptions<T, S extends FilterSpecMap> {
  filters: FiltersOf<S>;
  initialData?: T[];
  initialTotalCount?: number;
  onData?: (data: T[]) => void;
  onError?: (error: unknown) => void;
}

/**
 * The client-side half of a directory page: permission gate + paginated fetch,
 * both driven off one descriptor. Page/rowsPerPage state lives in
 * `usePaginatedList`; filters are owned by the caller and passed in.
 */
export function useDirectoryList<T, S extends FilterSpecMap>(
  descriptor: DirectoryDescriptor<T, S>,
  {
    filters,
    initialData,
    initialTotalCount,
    onData,
    onError,
  }: UseDirectoryListOptions<T, S>
) {
  const gate = useDirectoryAuthGate(descriptor);

  const list = usePaginatedList<T>({
    fetchPage: ({ skip, limit }) =>
      descriptor.list(
        new ApiClientFactory(),
        directoryListParams(descriptor, {
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
  };
}
