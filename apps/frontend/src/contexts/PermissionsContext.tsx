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
import { useSession } from 'next-auth/react';
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
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
  const [state, setState] = useState<AmbientPermissions>(DEFAULT_STATE);

  useEffect(() => {
    // Feature flags still loading ⇒ RBAC status unknown. Stay loading (so useCan
    // is fail-closed) rather than dropping to permissive, which would briefly
    // fail-open and flash EE nav unlocked→locked.
    if (featuresLoading) {
      setState(DEFAULT_STATE);
      return;
    }

    // RBAC off ⇒ role-level gating is inert. No request; useCan stays permissive.
    if (!rbacEnabled) {
      setState(DISABLED_STATE);
      return;
    }

    if (status !== 'authenticated' || !session?.session_token) {
      // Logout / session expiry: clear any prior permissions so they cannot
      // leak across an auth transition (fail-closed).
      setState(DEFAULT_STATE);
      return;
    }

    // Reset to loading whenever the token or scope changes so gated UI stays
    // hidden while the new set is in flight.
    setState({ ...DEFAULT_STATE, enabled: true });

    let cancelled = false;
    const client = new ApiClientFactory(
      session.session_token
    ).getPermissionsClient();

    client
      .getMyPermissions(activeProject?.id ?? undefined)
      .then(caps => {
        if (cancelled) return;
        setState({
          permitted_actions: caps,
          loading: false,
          error: null,
          enabled: true,
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const error = err instanceof Error ? err : new Error(String(err));
        setState({
          permitted_actions: [],
          loading: false,
          error,
          enabled: true,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [
    featuresLoading,
    rbacEnabled,
    status,
    session?.session_token,
    activeProject?.id,
  ]);

  const value = useMemo(() => state, [state]);

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
