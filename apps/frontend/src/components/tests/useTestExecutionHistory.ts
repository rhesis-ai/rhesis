'use client';

import { useQuery } from '@tanstack/react-query';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { testKeys } from '@/constants/query-keys';
import {
  fetchTestExecutionHistory,
  type TestExecutionHistoryRow,
} from './test-execution-history';

interface UseTestExecutionHistoryOptions {
  testId: string | undefined;
  enabled?: boolean;
  /** Server-prefetched rows; when present the hook skips its mount fetch. */
  initialRows?: TestExecutionHistoryRow[];
}

interface UseTestExecutionHistoryResult {
  rows: TestExecutionHistoryRow[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

const EMPTY_ROWS: TestExecutionHistoryRow[] = [];

export function useTestExecutionHistory({
  testId,
  enabled = true,
  initialRows,
}: UseTestExecutionHistoryOptions): UseTestExecutionHistoryResult {
  const isAuthenticated = useIsAuthenticated();

  const { data, isPending, error, refetch } = useQuery({
    queryKey: [...testKeys.detail(testId ?? ''), 'execution-history'],
    queryFn: () =>
      fetchTestExecutionHistory(new ApiClientFactory(), testId as string),
    enabled: enabled && isAuthenticated && !!testId,
    initialData: initialRows,
  });

  if (!testId) {
    return {
      rows: EMPTY_ROWS,
      loading: false,
      error: 'No test ID available',
      refetch: () => {},
    };
  }

  return {
    rows: data ?? EMPTY_ROWS,
    loading: enabled && isPending,
    error: error ? 'Failed to load execution history' : null,
    refetch: () => void refetch(),
  };
}
