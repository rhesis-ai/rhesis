'use client';

/**
 * Ambient (scope-level) authorization subject.
 *
 * `PermissionsProvider` fetches the caller's effective capabilities for the
 * active project scope from `GET /me/permissions?project_id=<active>` and
 * exposes them as an *ambient subject* — the same `WithPermittedActions` shape
 * carried by individual resources (comments, …). This is the scope half of the
 * unified affordance model: object-level affordances ride on the object; the
 * scope-level set rides here. Both are consumed through the single `can` /
 * `useCan` / `<Can>` primitive in `components/common/Can`.
 *
 * Fail-closed, mirroring `FeaturesContext`: empty while loading and on error,
 * and refetched on project switch. Kept on a dedicated endpoint (not folded
 * into the project resource) so permission freshness stays independent of
 * resource caching — see server_driven_affordances_1af9c705.plan.md (option B).
 *
 * Master switch: this scope-level (role) gating only applies when
 * `FeatureName.RBAC` is enabled. When off, `enabled` is false, no request is
 * made, and `useCan` is a permissive no-op — community nav/pages render exactly
 * as pre-RBAC. Object-level affordances (`can(subject, …)`) are unaffected: they
 * always reflect the resource's server-computed `permitted_actions`.
 */

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { useFeature, useFeaturesState } from '@/contexts/FeaturesContext';
import { FeatureName } from '@/constants/features';
import { permissionKeys } from '@/constants/query-keys';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { createContext, useContext, useMemo, type ReactNode } from 'react';
import type { WithPermittedActions } from '@/types/affordances';

export interface AmbientPermissions extends WithPermittedActions {
  permitted_actions: string[];
  loading: boolean;
  error: Error | null;
  /**
   * Whether scope-level (role) gating is active, i.e. `FeatureName.RBAC` is on.
   * When RBAC is *known* off (not loading), `useCan` is permissive and no
   * `/me/permissions` request is made. While feature flags are still loading the
   * status is unknown, so `loading` stays true and `useCan` is fail-closed.
   */
  enabled: boolean;
}

const DEFAULT_STATE: AmbientPermissions = {
  permitted_actions: [],
  loading: true,
  error: null,
  enabled: false,
};

/** Resolved state when RBAC is off: permissive, not loading, no request. */
const DISABLED_STATE: AmbientPermissions = {
  permitted_actions: [],
  loading: false,
  error: null,
  enabled: false,
};

const PermissionsContext = createContext<AmbientPermissions>(DISABLED_STATE);

export function PermissionsProvider({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const { activeProject } = useActiveProject();
  const { loading: featuresLoading } = useFeaturesState();
  const rbacEnabled = useFeature(FeatureName.RBAC);
  const sessionToken =
    status === 'authenticated' ? session?.session_token : undefined;
  // Prefer the stable user id, but fall back to the per-user session token so
  // the cache key is never shared across users even if `user.id` is missing.
  const userScope = session?.user?.id ?? sessionToken ?? '';

  const { data, isLoading, error, isSuccess } = useQuery({
    queryKey: permissionKeys.all(userScope, activeProject?.id ?? ''),
    queryFn: () =>
      new ApiClientFactory(sessionToken!)
        .getPermissionsClient()
        .getMyPermissions(activeProject?.id ?? undefined),
    enabled: !featuresLoading && rbacEnabled && !!sessionToken,
    staleTime: 5 * 60_000,
  });

  const value = useMemo<AmbientPermissions>(() => {
    if (featuresLoading) return DEFAULT_STATE;
    if (!rbacEnabled && !featuresLoading) return DISABLED_STATE;
    if (isLoading || (!isSuccess && !error))
      return { ...DEFAULT_STATE, enabled: true };
    if (error)
      return {
        permitted_actions: [],
        loading: false,
        error: error instanceof Error ? error : new Error(String(error)),
        enabled: true,
      };
    if (data)
      return {
        permitted_actions: data,
        loading: false,
        error: null,
        enabled: true,
      };
    return DEFAULT_STATE;
  }, [featuresLoading, rbacEnabled, isLoading, isSuccess, error, data]);

  return (
    <PermissionsContext.Provider value={value}>
      {children}
    </PermissionsContext.Provider>
  );
}

/**
 * The ambient subject: the caller's effective capabilities in the active
 * project scope, plus loading/error/enabled. Consume via `useCan(capability)`
 * rather than reading this directly in most cases.
 */
export function useAmbientPermissions(): AmbientPermissions {
  return useContext(PermissionsContext);
}
