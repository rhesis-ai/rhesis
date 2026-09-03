import { Capability } from '@/constants/capabilities';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import type { UsageResponse } from '@/utils/api-client/usage-client';
import { hasServerCapability } from '@/utils/server-permissions';
import { requireSession } from '@/utils/require-session';
import UsagePageClient from './components/UsagePageClient';

/**
 * Server component: fetches `GET /usage` before rendering so the Usage
 * dashboard arrives with data instead of a spinner. Gated on the same
 * capability the client checks; if not permitted or the fetch fails, the
 * client falls back to its own fetch (fail open).
 */
export default async function OrganizationUsagePage() {
  await requireSession();

  let initialUsage: UsageResponse | undefined;
  if (await hasServerCapability(Capability.Usage.READ)) {
    const factory = await createServerApiFactory();
    initialUsage = await factory
      .getUsageClient()
      .getUsage()
      .then(usage => JSON.parse(JSON.stringify(usage)) as UsageResponse)
      .catch(() => undefined);
  }

  return <UsagePageClient initialUsage={initialUsage} />;
}
