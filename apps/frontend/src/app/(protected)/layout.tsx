import { auth, getFreshAccessToken } from '@/auth';
import { headers } from 'next/headers';
import { FeatureName } from '@/constants/features';
import type { FeaturesResponse } from '@/utils/api-client/features-client';
import { fetchTermsStatusServer } from '@/utils/api-client/auth-client.server';
import type { TermsStatus } from '@/utils/api-client/auth-client';
import {
  getServerFeatures,
  getServerPermissions,
} from '@/utils/server-permissions';
import { ProtectedLayoutClient } from './ProtectedLayoutClient';

/**
 * Server-side layout that seeds `FeaturesProvider`, `PermissionsProvider`, and
 * `TermsAcceptanceGate` with data so they don't need a client-side fetch on
 * mount. Failures are swallowed -- client providers fall back to fetching.
 *
 * Uses `getServerFeatures`/`getServerPermissions` (React.cache-wrapped) so
 * nested server components (page.tsx via prefetchList/hasServerCapability)
 * share the same responses without issuing duplicate requests.
 */
export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth().catch(() => null);

  let initialFeatures: FeaturesResponse | null = null;
  let initialPermissions: string[] | null = null;
  let initialTermsStatus: TermsStatus | null = null;

  if (session && !session.error) {
    const { accessToken } = await getFreshAccessToken({
      headers: await headers(),
    });

    const [featuresResult, termsResult] = await Promise.allSettled([
      getServerFeatures(),
      accessToken ? fetchTermsStatusServer(accessToken) : Promise.resolve(null),
    ]);

    if (featuresResult.status === 'fulfilled') {
      initialFeatures = featuresResult.value;

      if (initialFeatures.enabled.includes(FeatureName.RBAC)) {
        try {
          initialPermissions = await getServerPermissions();
        } catch {
          // Ignore -- PermissionsProvider falls back to fetching on mount.
        }
      }
    }

    if (termsResult.status === 'fulfilled') {
      initialTermsStatus = termsResult.value;
    }
  }

  return (
    <ProtectedLayoutClient
      initialFeatures={initialFeatures}
      initialPermissions={initialPermissions}
      initialTermsStatus={initialTermsStatus}
    >
      {children}
    </ProtectedLayoutClient>
  );
}
