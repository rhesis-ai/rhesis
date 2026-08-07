'use client';

import { useMemo } from 'react';
import {
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query';
import {
  insightsFailedTestIdsKeys,
  insightsTestRunIdsKeys,
} from '@/constants/query-keys';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import { resolveInsightsTimeRange } from '@/app/(protected)/insights/types';
import { resolveInsightsQueryTestRunIds } from '@/app/(protected)/insights/utils/behavior-insights-utils';
import {
  fetchFailedTestIdsForInsights,
  type InsightsFailedTestsScope,
  type InsightsRunContextFilters,
  type InsightsTestOutcome,
} from '@/app/(protected)/insights/utils/insights-failed-tests';

export type InsightsFailedTestIdsFilters = InsightsRunContextFilters &
  InsightsFailedTestsScope;

export function toInsightsFailedTestIdsScope(
  filters: InsightsFailedTestIdsFilters
) {
  return {
    endpointId: filters.endpointId,
    runFilterMode: filters.runFilterMode,
    timeRange: resolveInsightsTimeRange(filters.timeRange),
    testRunIds: [...filters.testRunIds].sort(),
    ...(filters.behaviorId ? { behaviorId: filters.behaviorId } : {}),
    ...(filters.metricName ? { metricName: filters.metricName } : {}),
    ...(filters.topicName ? { topicName: filters.topicName } : {}),
    outcome: filters.outcome === 'all' ? 'all' : 'failed',
  };
}

function toInsightsTestRunIdsScope(filters: InsightsRunContextFilters) {
  return {
    endpointId: filters.endpointId,
    runFilterMode: filters.runFilterMode,
    timeRange: resolveInsightsTimeRange(filters.timeRange),
    testRunIds: [...filters.testRunIds].sort(),
  };
}

export async function fetchInsightsQueryTestRunIds(
  queryClient: QueryClient,
  filters: InsightsRunContextFilters
): Promise<string[]> {
  const normalized: InsightsRunContextFilters = {
    endpointId: filters.endpointId,
    runFilterMode: filters.runFilterMode,
    timeRange: resolveInsightsTimeRange(filters.timeRange),
    testRunIds: filters.testRunIds,
  };

  return queryClient.fetchQuery({
    queryKey: insightsTestRunIdsKeys.scope(
      toInsightsTestRunIdsScope(normalized)
    ),
    queryFn: () => resolveInsightsQueryTestRunIds(normalized),
  });
}

async function insightsFailedTestIdsQueryFn(
  queryClient: QueryClient,
  filters: InsightsFailedTestIdsFilters
): Promise<string[]> {
  const testRunIds = await fetchInsightsQueryTestRunIds(queryClient, filters);
  return fetchFailedTestIdsForInsights({
    ...filters,
    timeRange: resolveInsightsTimeRange(filters.timeRange),
    testRunIds,
  });
}

export async function fetchInsightsFailedTestIds(
  queryClient: QueryClient,
  filters: InsightsFailedTestIdsFilters
): Promise<string[]> {
  return queryClient.fetchQuery({
    queryKey: insightsFailedTestIdsKeys.scope(
      toInsightsFailedTestIdsScope(filters)
    ),
    queryFn: () => insightsFailedTestIdsQueryFn(queryClient, filters),
  });
}

export function prefetchInsightsFailedTestIds(
  queryClient: QueryClient,
  filters: InsightsFailedTestIdsFilters
): Promise<void> {
  return queryClient.prefetchQuery({
    queryKey: insightsFailedTestIdsKeys.scope(
      toInsightsFailedTestIdsScope(filters)
    ),
    queryFn: () => insightsFailedTestIdsQueryFn(queryClient, filters),
  });
}

export function useInsightsFailedTestIds(
  filters: InsightsFailedTestIdsFilters | null | undefined,
  enabled = true
) {
  const queryClient = useQueryClient();
  const isAuthenticated = useIsAuthenticated();

  const scope = useMemo(
    () => (filters ? toInsightsFailedTestIdsScope(filters) : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- field-level deps; testRunIds by value
    [
      filters?.endpointId,
      filters?.runFilterMode,
      filters?.timeRange,
      filters?.testRunIds?.join(','),
      filters?.behaviorId,
      filters?.metricName,
      filters?.topicName,
      filters?.outcome,
    ]
  );

  return useQuery({
    queryKey: scope
      ? insightsFailedTestIdsKeys.scope(scope)
      : insightsFailedTestIdsKeys.all(),
    queryFn: () => insightsFailedTestIdsQueryFn(queryClient, filters!),
    enabled: enabled && isAuthenticated && !!filters?.endpointId && !!scope,
  });
}

export function insightsOverallFailedScope(
  filters: InsightsRunContextFilters,
  outcome: InsightsTestOutcome = 'failed'
): InsightsFailedTestIdsFilters {
  return {
    endpointId: filters.endpointId,
    runFilterMode: filters.runFilterMode,
    timeRange: resolveInsightsTimeRange(filters.timeRange),
    testRunIds: filters.testRunIds,
    outcome,
  };
}
