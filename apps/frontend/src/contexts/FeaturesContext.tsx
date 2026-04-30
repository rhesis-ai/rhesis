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
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { LicenseInfo } from '@/utils/api-client/features-client';
import { useSession } from 'next-auth/react';
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

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
  const [state, setState] = useState<FeaturesState>(DEFAULT_STATE);

  useEffect(() => {
    // Wait for the session to resolve before attempting the fetch.
    // Unauthenticated users never reach protected layouts, but if the
    // session is still loading we stay in the fail-closed default state.
    if (status !== 'authenticated' || !session?.session_token) {
      return;
    }

    // Reset to loading each time the token changes (e.g. after re-login).
    // Without this the component stays in the previous error/stale state
    // while the new fetch is in flight, keeping gated UI hidden.
    setState(DEFAULT_STATE);

    let cancelled = false;
    const client = new ApiClientFactory(session.session_token).getFeaturesClient();

    client
      .getFeatures()
      .then(response => {
        if (cancelled) return;
        setState({
          license: response.license,
          enabled: new Set<string>(response.enabled),
          loading: false,
          error: null,
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const error = err instanceof Error ? err : new Error(String(err));
        setState({
          license: null,
          enabled: new Set<string>(),
          loading: false,
          error,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [status, session?.session_token]);

  // Stable reference avoids re-rendering every consumer on unrelated
  // parent re-renders.
  const value = useMemo(() => state, [state]);

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
