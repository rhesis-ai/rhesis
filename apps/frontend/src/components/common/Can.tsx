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
 * Fail-closed while the scope set is loading.
 */
export function useCan(capability: string): boolean {
  const ambient = useAmbientPermissions();
  if (ambient.loading) return false;
  return can(ambient, capability);
}

/**
 * Declarative gate. Pass `subject` for an object-level check; omit it for an
 * ambient (scope) check. Renders `children` when allowed, `fallback` otherwise.
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
  const allowed =
    subject !== undefined
      ? can(subject, capability)
      : !ambient.loading && can(ambient, capability);
  return <>{allowed ? children : fallback}</>;
}
