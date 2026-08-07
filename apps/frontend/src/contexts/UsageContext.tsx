'use client';

/**
 * Read-only usage accounting: per-resource counters, limits, and the
 * current billing period, for the org usage dashboard tab.
 *
 * Mirrors `FeaturesContext`'s caching pattern: `useQuery` scoped by
 * `userScope`, with `staleTime` matching the other ambient providers.
 *
 * Unlike `FeaturesProvider`, this is mounted by the Usage page itself rather
 * than the protected layout -- nothing else reads usage, and `GET /usage`
 * is too costly to issue on every protected navigation. That also means
 * there is no SSR-seeded `initialData`: the page shows its loading
 * skeleton for one round trip instead.
 *
 * Fail-closed, same as `FeaturesContext`/`PermissionsContext`: `resources`
 * is empty during the initial fetch and on error, never a stale/default
 * numeric guess.
 */

import { usageKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { UsageResourceItem } from '@/utils/api-client/usage-client';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { isAuthenticated, useUserScope } from '@/hooks/useIsAuthenticated';

export interface UsageState {
  resources: Readonly<Record<string, UsageResourceItem>>;
  edition: string | null;
  loading: boolean;
  error: Error | null;
}

const DEFAULT_STATE: UsageState = {
  resources: {},
  edition: null,
  loading: true,
  error: null,
};

const UsageContext = createContext<UsageState>(DEFAULT_STATE);

export function UsageProvider({ children }: { children: ReactNode }) {
  const { status } = useSession();
  const userScope = useUserScope();

  const { data, isLoading, error } = useQuery({
    queryKey: usageKeys.all(userScope),
    queryFn: () => new ApiClientFactory().getUsageClient().getUsage(),
    // `!!userScope` closes the gap where `status` flips to 'authenticated'
    // before `userScope` reflects the real user id — without it the query
    // could run (and cache) under the `''` scope key.
    enabled: isAuthenticated(status) && !!userScope,
    staleTime: 5 * 60_000,
  });

  const value = useMemo<UsageState>(() => {
    if (!isAuthenticated(status) || isLoading) return DEFAULT_STATE;
    if (error)
      return {
        resources: {},
        edition: null,
        loading: false,
        error: error instanceof Error ? error : new Error(String(error)),
      };
    if (!data) return DEFAULT_STATE;
    return {
      resources: data.resources,
      edition: data.edition,
      loading: false,
      error: null,
    };
  }, [data, isLoading, error, status]);

  return (
    <UsageContext.Provider value={value}>{children}</UsageContext.Provider>
  );
}

/**
 * Full state accessor: resources, edition, loading, error.
 */
export function useUsage(): UsageState {
  return useContext(UsageContext);
}

/**
 * Usage for a single resource (e.g. `QuotaResource.TEST_EXECUTIONS` value),
 * or `null` while loading, on error, or if the resource is absent from the
 * response.
 */
export function useResourceUsage(resource: string): UsageResourceItem | null {
  const { resources, loading } = useContext(UsageContext);
  if (loading) return null;
  return resources[resource] ?? null;
}
