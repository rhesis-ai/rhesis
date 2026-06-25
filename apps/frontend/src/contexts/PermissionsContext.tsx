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
 */

import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
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
}

const DEFAULT_STATE: AmbientPermissions = {
  permitted_actions: [],
  loading: true,
  error: null,
};

const PermissionsContext = createContext<AmbientPermissions>(DEFAULT_STATE);

export function PermissionsProvider({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const { activeProject } = useActiveProject();
  const [state, setState] = useState<AmbientPermissions>(DEFAULT_STATE);

  useEffect(() => {
    if (status !== 'authenticated' || !session?.session_token) {
      // Logout / session expiry: clear any prior permissions so they cannot
      // leak across an auth transition (fail-closed).
      setState(DEFAULT_STATE);
      return;
    }

    // Reset to loading whenever the token or scope changes so gated UI stays
    // hidden while the new set is in flight.
    setState(DEFAULT_STATE);

    let cancelled = false;
    const client = new ApiClientFactory(
      session.session_token
    ).getPermissionsClient();

    client
      .getMyPermissions(activeProject?.id ?? undefined)
      .then(caps => {
        if (cancelled) return;
        setState({ permitted_actions: caps, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const error = err instanceof Error ? err : new Error(String(err));
        setState({ permitted_actions: [], loading: false, error });
      });

    return () => {
      cancelled = true;
    };
  }, [status, session?.session_token, activeProject?.id]);

  const value = useMemo(() => state, [state]);

  return (
    <PermissionsContext.Provider value={value}>
      {children}
    </PermissionsContext.Provider>
  );
}

/**
 * The ambient subject: the caller's effective capabilities in the active
 * project scope, plus loading/error. Consume via `useCan(capability)` rather
 * than reading this directly in most cases.
 */
export function useAmbientPermissions(): AmbientPermissions {
  return useContext(PermissionsContext);
}
