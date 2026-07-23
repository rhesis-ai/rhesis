import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { getServerActiveProjectId } from '@/utils/server-active-project';
import { FeatureName } from '@/constants/features';
import type { FeaturesResponse } from '@/utils/api-client/features-client';
import { ProtectedLayoutClient } from './ProtectedLayoutClient';

/**
 * Server-side counterpart of `ProtectedLayoutClient`. Fetches `GET /features`
 * and, when RBAC is on, `GET /me/permissions` for the active project — the
 * same two calls `FeaturesProvider`/`PermissionsProvider` would otherwise make
 * on mount — so the nav-gating capability set is already known on first paint.
 * Without this, `useCan` reports "unknown" (fail-closed) for one round trip on
 * every hard load, hiding every gated nav item until the client fetch resolves.
 *
 * Mirrors the `initialActiveProject`/`initialOrganization` seeding already
 * done in the root `app/layout.tsx`. Failures here are swallowed — the client
 * providers fall back to fetching normally, same as that existing pattern.
 */
export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth().catch(() => null);

  let initialFeatures: FeaturesResponse | null = null;
  let initialPermissions: string[] | null = null;

  if (session && !session.error) {
    try {
      const projectId = await getServerActiveProjectId();
      const factory = await createServerApiFactory();

      initialFeatures = await factory.getFeaturesClient().getFeatures();

      if (initialFeatures.enabled.includes(FeatureName.RBAC)) {
        initialPermissions = await factory
          .getPermissionsClient()
          .getMyPermissions(projectId);
      }
    } catch {
      // Ignore — client providers will fetch on mount.
    }
  }

  return (
    <ProtectedLayoutClient
      initialFeatures={initialFeatures}
      initialPermissions={initialPermissions}
    >
      {children}
    </ProtectedLayoutClient>
  );
}
