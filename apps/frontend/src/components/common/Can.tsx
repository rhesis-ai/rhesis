'use client';

/**
 * The single authorization primitive.
 *
 * `can(subject, capability)` asks one question — "may the caller perform
 * `capability` on this subject?" — by testing membership in the subject's
 * server-resolved `permitted_actions`. A subject is anything carrying
 * affordances: an object (a comment) or the ambient scope (the active project).
 *
 * This subsumes both object-level and scope-level (role) checks under one model
 * and one vocabulary (full capability strings). The backend is the single
 * source of truth; the frontend only does set membership — a thin injection. No
 * ownership math, no `:own` logic, no per-resource policy lives here.
 */

import React, { type ReactNode } from 'react';
import type { WithPermittedActions } from '@/types/affordances';
import { can } from '@/utils/affordances';
import { useAmbientPermissions } from '@/contexts/PermissionsContext';

export { can } from '@/utils/affordances';

/**
 * Ambient check against the active-project scope — for no-object decisions like
 * nav gating, page access, and create buttons: `useCan(Capability.Metric.READ)`.
 *
 * Fail-closed while the RBAC status / scope set is still loading (covers the
 * feature-flag load window — no fail-open flash). Once resolved: permissive no-op
 * when RBAC is off (scope-level gating is an EE concern, so community renders
 * exactly as pre-RBAC); otherwise a membership check against the scope set.
 */
export function useCan(capability: string): boolean {
  const ambient = useAmbientPermissions();
  if (ambient.loading) return false;
  if (!ambient.enabled) return true;
  return can(ambient, capability);
}

/**
 * Loading-aware variant of {@link useCan} for page/section read guards.
 *
 * Returns `loading` so callers can distinguish "not yet resolved" from "denied"
 * and avoid flashing an Access-Denied screen during the permission-fetch window
 * (which exists even for community/RBAC-off users while feature flags load).
 * Guard sites should render a neutral loading state while `loading` is true and
 * only fall through to `<AccessDenied />` once `allowed` is known false.
 *
 * `allowed` matches `useCan` exactly: fail-closed while loading, permissive when
 * RBAC is off, otherwise a membership check against the ambient scope set.
 */
export function useCanWithStatus(capability: string): {
  allowed: boolean;
  loading: boolean;
} {
  const ambient = useAmbientPermissions();
  if (ambient.loading) return { allowed: false, loading: true };
  if (!ambient.enabled) return { allowed: true, loading: false };
  return { allowed: can(ambient, capability), loading: false };
}

/**
 * Declarative gate. Pass `subject` for an object-level check (always reflects the
 * resource's `permitted_actions`); omit it for an ambient (scope) check, which is
 * a permissive no-op when RBAC is off. Renders `children` when allowed.
 */
export function Can({
  capability,
  subject,
  fallback = null,
  children,
}: {
  capability: string;
  subject?: WithPermittedActions | null;
  fallback?: ReactNode;
  children: ReactNode;
}) {
  const ambient = useAmbientPermissions();
  let allowed: boolean;
  if (subject !== undefined) {
    // Object-level: always reflects the resource's server-computed affordances.
    allowed = can(subject, capability);
  } else if (ambient.loading) {
    // Ambient + RBAC status/scope unknown: fail-closed (no fail-open flash).
    allowed = false;
  } else if (!ambient.enabled) {
    // Ambient + RBAC off: permissive no-op.
    allowed = true;
  } else {
    allowed = can(ambient, capability);
  }
  return <>{allowed ? children : fallback}</>;
}
