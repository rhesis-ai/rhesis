'use client';

/**
 * Usage for a specific past billing period, or the current one when
 * `periodStart` is `null`. The `null` case delegates to `UsageContext`
 * rather than issuing a second fetch for data the SSR-seeded context
 * query already has.
 */

import { usageKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useUsage, type UsageState } from '@/contexts/UsageContext';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { useMemo } from 'react';
import { isAuthenticated, useUserScope } from '@/hooks/useIsAuthenticated';

const LOADING_STATE: UsageState = {
  resources: {},
  edition: null,
  plan: null,
  loading: true,
  error: null,
};

export function useUsageForPeriod(periodStart: string | null): UsageState {
  const current = useUsage();
  const { status } = useSession();
  const userScope = useUserScope();

  const { data, isLoading, error } = useQuery({
    queryKey: usageKeys.forPeriod(userScope, periodStart ?? ''),
    queryFn: () =>
      new ApiClientFactory()
        .getUsageClient()
        .getUsage(periodStart ?? undefined),
    enabled: periodStart !== null && isAuthenticated(status) && !!userScope,
    staleTime: 5 * 60_000,
  });

  return useMemo<UsageState>(() => {
    if (periodStart === null) return current;
    if (!isAuthenticated(status) || isLoading) return LOADING_STATE;
    if (error) {
      return {
        resources: {},
        edition: null,
        plan: null,
        loading: false,
        error: error instanceof Error ? error : new Error(String(error)),
      };
    }
    if (!data) return LOADING_STATE;
    return {
      resources: data.resources,
      edition: data.edition,
      plan: data.plan ?? null,
      loading: false,
      error: null,
    };
  }, [periodStart, current, data, isLoading, error, status]);
}
