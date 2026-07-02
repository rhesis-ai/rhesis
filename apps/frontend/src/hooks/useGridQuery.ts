'use client';

import { useQuery, keepPreviousData } from '@tanstack/react-query';

export interface UseGridQueryOptions<T> {
  queryKey: readonly unknown[];
  queryFn: () => Promise<T>;
  enabled?: boolean;
}

export function useGridQuery<T>({
  queryKey,
  queryFn,
  enabled = true,
}: UseGridQueryOptions<T>) {
  return useQuery<T>({
    queryKey,
    queryFn,
    enabled,
    placeholderData: keepPreviousData,
  });
}
