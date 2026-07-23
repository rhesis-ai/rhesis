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
import type {
  LicenseInfo,
  FeaturesResponse,
} from '@/utils/api-client/features-client';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';

interface FeaturesState {
  license: LicenseInfo | null;
  enabled: ReadonlySet<string>;
  warnings: Readonly<Record<string, string>>;
  loading: boolean;
  error: Error | null;
}

const DEFAULT_STATE: FeaturesState = {
  license: null,
  enabled: new Set<string>(),
  warnings: {},
  loading: true,
  error: null,
};

const FeaturesContext = createContext<FeaturesState>(DEFAULT_STATE);

export function FeaturesProvider({
  children,
  initialFeatures = null,
}: {
  children: ReactNode;
  /**
   * Server-fetched `GET /features` result (see `(protected)/layout.tsx`),
   * seeded as this query's `initialData` so `loading` is already `false` on
   * the very first client render instead of flashing "no features enabled"
   * for one round trip. `null` (no session server-side, or the fetch failed)
   * falls back to the normal client-side fetch.
   */
  initialFeatures?: FeaturesResponse | null;
}) {
  const { data: session, status } = useSession();
  const userScope = session?.user?.id ?? '';

  const { data, isLoading, error } = useQuery({
    queryKey: featureKeys.all(userScope),
    queryFn: () => new ApiClientFactory().getFeaturesClient().getFeatures(),
    enabled: isAuthenticated(status),
    staleTime: 5 * 60_000,
    ...(initialFeatures ? { initialData: initialFeatures } : {}),
  });

  const value = useMemo<FeaturesState>(() => {
    // Fail-closed while the session is still resolving or the query is idle/
    // in-flight. A disabled react-query (enabled: false) reports isLoading=false
    // with data=undefined, so we must gate on the auth status explicitly --
    // otherwise the idle state would be mistaken for "loaded, no features" and
    // gated UI (and downstream RBAC permissions) would flash permissive.
    if (!isAuthenticated(status) || isLoading) return DEFAULT_STATE;
    if (error)
      return {
        license: null,
        enabled: new Set<string>(),
        warnings: {},
        loading: false,
        error: error instanceof Error ? error : new Error(String(error)),
      };
    if (!data) return DEFAULT_STATE;
    return {
      license: data.license,
      enabled: new Set<string>(data.enabled),
      warnings: data.warnings ?? {},
      loading: false,
      error: null,
    };
  }, [data, isLoading, error, status]);

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
 * Returns the warning message for a feature, or null if the feature
 * is fully operational. Use this to show a banner when a feature is
 * licensed but its backing infrastructure is not yet configured.
 */
export function useFeatureWarning(name: FeatureName): string | null {
  const { warnings, loading } = useContext(FeaturesContext);
  if (loading) return null;
  return warnings[name] ?? null;
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
