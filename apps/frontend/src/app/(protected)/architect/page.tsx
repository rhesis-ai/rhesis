import { Metadata } from 'next';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetch } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import ArchitectClient from './components/ArchitectClient';
import { requireSession } from '@/utils/require-session';

export const metadata: Metadata = {
  title: 'Architect',
};

/**
 * Server component: fetches the session list and the welcome screen's
 * endpoint check before rendering, so the sidebar and the suggestion chips
 * arrive with the page. Each fails open to "no initial data" so the client
 * falls back to its own fetch.
 */
export default async function ArchitectPage() {
  await requireSession();

  const factory = await createServerApiFactory();
  const [initialSessions, initialEndpoints] = await Promise.all([
    prefetch(Capability.Architect.READ, () =>
      factory.getArchitectClient().getSessions()
    ),
    // Same `limit: 1` query as `useProjectNeedsEndpoint`.
    prefetch(Capability.Endpoint.READ, async () => {
      const response = await factory
        .getEndpointsClient()
        .getEndpoints({ limit: 1 });
      return response.data || [];
    }),
  ]);

  return (
    <ArchitectClient
      initialSessions={initialSessions}
      initialEndpoints={initialEndpoints}
    />
  );
}
