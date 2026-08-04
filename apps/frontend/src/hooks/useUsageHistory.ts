'use client';

/**
 * Monthly usage history for flow resources over the trailing `months`
 * months, for the Usage tab's timespan filter + line charts.
 *
 * Not part of `UsageContext`/`UsageProvider`: `months` is a runtime-
 * selectable filter value, not something the protected layout can seed
 * once at SSR time the way the current-period snapshot is.
 */

import { usageKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { UsageHistoryPoint } from '@/utils/api-client/usage-client';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { useMemo } from 'react';
import { isAuthenticated, useUserScope } from '@/hooks/useIsAuthenticated';

export interface UsageHistoryState {
  resources: Readonly<Record<string, UsageHistoryPoint[]>>;
  loading: boolean;
  error: Error | null;
}

const DEFAULT_STATE: UsageHistoryState = {
  resources: {},
  loading: true,
  error: null,
};

export function useUsageHistory(months: number): UsageHistoryState {
  const { status } = useSession();
  const userScope = useUserScope();

  const { data, isLoading, error } = useQuery({
    queryKey: usageKeys.history(userScope, months),
    queryFn: () =>
      new ApiClientFactory().getUsageClient().getUsageHistory(months),
    // Same `!!userScope` guard as UsageContext: closes the gap where
    // `status` flips to 'authenticated' before `userScope` reflects the
    // real user id.
    enabled: isAuthenticated(status) && !!userScope,
    staleTime: 5 * 60_000,
  });

  return useMemo<UsageHistoryState>(() => {
    if (!isAuthenticated(status) || isLoading) return DEFAULT_STATE;
    if (error) {
      return {
        resources: {},
        loading: false,
        error: error instanceof Error ? error : new Error(String(error)),
      };
    }
    return { resources: data?.resources ?? {}, loading: false, error: null };
  }, [data, isLoading, error, status]);
}
