import { cache } from 'react';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { getServerActiveProjectId } from '@/utils/server-active-project';
import { FeatureName } from '@/constants/features';
import type { FeaturesResponse } from '@/utils/api-client/features-client';
import { can } from '@/utils/affordances';

/**
 * Cached server-side fetchers for features and permissions. `React.cache()`
 * deduplicates within a single RSC render pass, so `layout.tsx` and
 * `page.tsx` (via `prefetchList` / `hasServerCapability`) share one
 * `GET /features` and one `GET /me/permissions` call instead of two each.
 */
export const getServerFeatures = cache(async (): Promise<FeaturesResponse> => {
  const factory = await createServerApiFactory();
  return factory.getFeaturesClient().getFeatures();
});

export const getServerPermissions = cache(async (): Promise<string[]> => {
  const factory = await createServerApiFactory();
  const projectId = await getServerActiveProjectId();
  return factory.getPermissionsClient().getMyPermissions(projectId);
});

/**
 * Server-side counterpart of `useCan`/`useCanWithStatus` for gating a page's
 * initial server-rendered fetch, not just its client-side render.
 *
 * When the RBAC feature is off, every ambient check is a permissive no-op
 * (matches `useCan`'s behavior); when it's on, checks membership in
 * `GET /me/permissions` for the active project via the same `can()`
 * primitive `useCan`/`useCanWithStatus` use client-side, so server and client
 * can't independently drift on what "has this capability" means. Fails
 * closed (returns `false`) on any error, since the caller uses this to
 * decide whether it's safe to fetch and expose data.
 */
export async function hasServerCapability(
  capability: string
): Promise<boolean> {
  try {
    const features = await getServerFeatures();

    if (!features.enabled.includes(FeatureName.RBAC)) {
      return true;
    }

    const permissions = await getServerPermissions();
    return can({ permitted_actions: permissions }, capability);
  } catch {
    return false;
  }
}
