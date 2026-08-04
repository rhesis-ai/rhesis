import { auth, getFreshAccessToken } from '@/auth';
import { headers } from 'next/headers';
import { FeatureName } from '@/constants/features';
import type { FeaturesResponse } from '@/utils/api-client/features-client';
import type { UsageResponse } from '@/utils/api-client/usage-client';
import { fetchTermsStatusServer } from '@/utils/api-client/auth-client.server';
import type { TermsStatus } from '@/utils/api-client/auth-client';
import {
  getServerFeatures,
  getServerPermissions,
  getServerUsage,
} from '@/utils/server-permissions';
import { ProtectedLayoutClient } from './ProtectedLayoutClient';

/**
 * Server-side layout that seeds `FeaturesProvider`, `UsageProvider`,
 * `PermissionsProvider`, and `TermsAcceptanceGate` with data so they don't
 * need a client-side fetch on mount. Failures are swallowed -- client
 * providers fall back to fetching.
 *
 * Uses `getServerFeatures`/`getServerPermissions`/`getServerUsage`
 * (React.cache-wrapped) so nested server components (page.tsx via
 * prefetchList/hasServerCapability) share the same responses without
 * issuing duplicate requests.
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
  let initialUsage: UsageResponse | null = null;

  if (session && !session.error) {
    const { accessToken } = await getFreshAccessToken({
      headers: await headers(),
    });

    const [featuresResult, termsResult, usageResult] = await Promise.allSettled(
      [
        getServerFeatures(),
        accessToken
          ? fetchTermsStatusServer(accessToken)
          : Promise.resolve(null),
        getServerUsage(),
      ]
    );

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

    if (usageResult.status === 'fulfilled') {
      initialUsage = usageResult.value;
    }
  }

  return (
    <ProtectedLayoutClient
      initialFeatures={initialFeatures}
      initialPermissions={initialPermissions}
      initialTermsStatus={initialTermsStatus}
      initialUsage={initialUsage}
    >
      {children}
    </ProtectedLayoutClient>
  );
}
