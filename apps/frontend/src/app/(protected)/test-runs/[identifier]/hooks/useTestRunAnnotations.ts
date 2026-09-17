'use client';

import { useQuery } from '@tanstack/react-query';
import { annotationKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import type { Annotation } from '@/utils/api-client/interfaces/annotation';
import type { PaginatedResponse } from '@/utils/api-client/interfaces/pagination';

/** The endpoint's own cap, and far more than a run accumulates. */
const PAGE_SIZE = 100;

/**
 * Every annotation recorded across a test run, and how many there are.
 *
 * The tab and the count badge on its nav share this one query key, so the
 * badge is there before the tab is ever opened, opening it costs no second
 * request, and adding an annotation moves both at once.
 *
 * The count is the server's total rather than the rendered rows, so it stays
 * right for a run that outgrows the single page the tab lists.
 */
export function useTestRunAnnotations(testRunId: string): {
  annotations: Annotation[];
  count: number;
  isLoading: boolean;
} {
  const isAuthenticated = useIsAuthenticated();

  const { data, isLoading } = useQuery<PaginatedResponse<Annotation>>({
    queryKey: annotationKeys.list(`test_run:${testRunId}`),
    queryFn: () =>
      new ApiClientFactory().getAnnotationsClient().getAnnotations({
        test_run_id: testRunId,
        sort_by: 'updated_at',
        sort_order: 'desc',
        limit: PAGE_SIZE,
      }),
    enabled: isAuthenticated && !!testRunId,
  });

  return {
    annotations: data?.data ?? [],
    count: data?.pagination.totalCount ?? 0,
    isLoading,
  };
}
