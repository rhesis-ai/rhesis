'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';

export interface UseGridQueryOptions<T> {
  queryKey: readonly unknown[];
  queryFn: () => Promise<T>;
  enabled?: boolean;
  /** Override the app-wide staleTime (e.g. 0 for lists that must stay fresh). */
  staleTime?: number;
  /** Shown when the query fails with a non-Error rejection. */
  errorFallbackMessage?: string;
}

/**
 * Wraps useQuery for grid/list components with a dismissible error message.
 *
 * `errorMessage` surfaces `error.message` (falling back to
 * `errorFallbackMessage`) and clears when a new query attempt starts or the
 * caller calls `dismissError`.
 */
export function useGridQuery<T>({
  queryKey,
  queryFn,
  enabled = true,
  staleTime,
  errorFallbackMessage = 'Failed to load data',
}: UseGridQueryOptions<T>) {
  const query = useQuery<T>({
    queryKey,
    queryFn,
    enabled,
    placeholderData: keepPreviousData,
    ...(staleTime !== undefined ? { staleTime } : {}),
  });

  const [dismissed, setDismissed] = useState(false);
  const lastErrorRef = useRef<unknown>(null);

  useEffect(() => {
    if (query.error !== lastErrorRef.current) {
      lastErrorRef.current = query.error;
      setDismissed(false);
    }
  }, [query.error]);

  const errorMessage =
    query.error && !dismissed
      ? query.error instanceof Error
        ? query.error.message
        : errorFallbackMessage
      : null;

  return {
    ...query,
    errorMessage,
    dismissError: () => setDismissed(true),
  };
}
