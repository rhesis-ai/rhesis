import { Capability } from '@/constants/capabilities';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import type { UsageResponse } from '@/utils/api-client/usage-client';
import { prefetch } from '@/utils/server-prefetch';
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

  const initialUsage = await prefetch<UsageResponse>(
    Capability.Usage.READ,
    async () => (await createServerApiFactory()).getUsageClient().getUsage()
  );

  return <UsagePageClient initialUsage={initialUsage} />;
}
