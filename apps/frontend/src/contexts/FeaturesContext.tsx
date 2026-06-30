'use client';

/**
 * Central client-side feature gating primitive.
 *
 * `FeaturesProvider` fetches the current user's enabled features from
 * `GET /features` once on mount and exposes them via `useFeature` and
 * `<FeatureGate>`. Semantics are deliberately fail-closed:
 *
 * - During the initial fetch, `useFeature` returns `false` so gated UI
 *   never flashes before being hidden.
 * - On fetch error, every feature is treated as disabled. The error is
 *   surfaced via `useFeaturesState` for diagnostics or toast handling.
 *
 * Call sites always reference the `FeatureName` constant rather than
 * magic strings -- TypeScript catches typos that would otherwise fail
 * silently at runtime.
 */

import { FeatureName } from '@/constants/features';
import { featureKeys } from '@/constants/query-keys';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { LicenseInfo } from '@/utils/api-client/features-client';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { createContext, useContext, useMemo, type ReactNode } from 'react';

interface FeaturesState {
  license: LicenseInfo | null;
  enabled: ReadonlySet<string>;
  loading: boolean;
  error: Error | null;
}

const DEFAULT_STATE: FeaturesState = {
  license: null,
  enabled: new Set<string>(),
  loading: true,
  error: null,
};

const FeaturesContext = createContext<FeaturesState>(DEFAULT_STATE);

export function FeaturesProvider({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const sessionToken =
    status === 'authenticated' ? session?.session_token : undefined;
  // Prefer the stable user id, but fall back to the per-user session token so
  // the cache key is never shared across users even if `user.id` is missing.
  const userScope = session?.user?.id ?? sessionToken ?? '';

  const { data, isLoading, error } = useQuery({
    queryKey: featureKeys.all(userScope),

  const { data, isLoading, error } = useQuery({
    queryKey: featureKeys.all(),
    queryFn: () =>
      new ApiClientFactory(sessionToken!).getFeaturesClient().getFeatures(),
    enabled: !!sessionToken,
    staleTime: 5 * 60_000,
  });

  const value = useMemo<FeaturesState>(() => {
    // Fail-closed while the session is still resolving or the query is idle/
    // in-flight. A disabled react-query (enabled: false) reports isLoading=false
    // with data=undefined, so we must gate on sessionToken explicitly --
    // otherwise the idle state would be mistaken for "loaded, no features" and
    // gated UI (and downstream RBAC permissions) would flash permissive.
    if (!sessionToken || isLoading) return DEFAULT_STATE;
    if (isLoading || !data) return DEFAULT_STATE;
    if (isLoading) return DEFAULT_STATE;
    if (error)
      return {
        license: null,
        enabled: new Set<string>(),
        loading: false,
        error: error instanceof Error ? error : new Error(String(error)),
      };
    if (!data) return DEFAULT_STATE;
    return {
      license: data.license,
      enabled: new Set<string>(data.enabled),
      loading: false,
      error: null,
    };
  }, [sessionToken, data, isLoading, error]);
  }, [data, isLoading, error]);

  return (
    <FeaturesContext.Provider value={value}>
      {children}
    </FeaturesContext.Provider>
  );
}

/**
 * Returns true iff the feature is enabled for the current user's org.
 * Fail-closed: returns false while loading or on fetch error.
 */
export function useFeature(name: FeatureName): boolean {
  const { enabled, loading } = useContext(FeaturesContext);
  if (loading) return false;
  return enabled.has(name);
}

/**
 * Full state accessor for advanced consumers (license badges, error
 * toasts, loading spinners).
 */
export function useFeaturesState(): FeaturesState {
  return useContext(FeaturesContext);
}

/**
 * Declarative conditional renderer. Renders `children` when `feature`
 * is enabled, `fallback` otherwise.
 */
export function FeatureGate({
  feature,
  fallback = null,
  children,
}: {
  feature: FeatureName;
  fallback?: ReactNode;
  children: ReactNode;
}) {
  const enabled = useFeature(feature);
  return <>{enabled ? children : fallback}</>;
}
