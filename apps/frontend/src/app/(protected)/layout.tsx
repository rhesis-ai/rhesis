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
 * Server-side layout that seeds `FeaturesProvider`, `PermissionsProvider`,
 * and `TermsAcceptanceGate` with data so they don't need a client-side fetch
 * on mount. Failures are swallowed -- client providers fall back to fetching.
 *
 * Uses `getServerFeatures`/`getServerPermissions` (React.cache-wrapped) so
 * nested server components (page.tsx via prefetchList/hasServerCapability)
 * share the same responses without issuing duplicate requests.
 *
 * `GET /usage` has no server seed here (unlike features/permissions):
 * `UsageProvider` is mounted client-side in `ProtectedLayoutClient` so
 * `QuotaBanner` and execute-gating (`RunDrawer`) can read it anywhere in
 * the app. The cost (a license lookup plus four counting queries) is paid
 * once per `UsageContext`'s 5-minute `staleTime` window, not per
 * navigation. Only the Usage page seeds it, from its own server component.
 *
 * That is also why the org's plan rides on `GET /features` rather than
 * `GET /usage`: it is needed on first paint (the sidebar's plan row) and is
 * free to compute, so it belongs on the response already seeded here instead
 * of forcing a seed of the expensive one.
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
