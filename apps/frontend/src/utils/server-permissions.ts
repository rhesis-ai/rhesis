import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { getServerActiveProjectId } from '@/utils/server-active-project';
import { FeatureName } from '@/constants/features';

/**
 * Server-side counterpart of `useCan`/`useCanWithStatus` for gating a page's
 * initial server-rendered fetch, not just its client-side render.
 *
 * Mirrors `(protected)/layout.tsx`'s RBAC bootstrap: when the RBAC feature is
 * off, every ambient check is a permissive no-op (matches `useCan`'s
 * behavior); when it's on, checks membership in `GET /me/permissions` for the
 * active project. Fails closed (returns `false`) on any error, since the
 * caller uses this to decide whether it's safe to fetch and expose data.
 */
export async function hasServerCapability(capability: string): Promise<boolean> {
  try {
    const factory = await createServerApiFactory();
    const features = await factory.getFeaturesClient().getFeatures();

    if (!features.enabled.includes(FeatureName.RBAC)) {
      return true;
    }

    const projectId = await getServerActiveProjectId();
    const permissions = await factory
      .getPermissionsClient()
      .getMyPermissions(projectId);
    return permissions.includes(capability);
  } catch {
    return false;
  }
}
