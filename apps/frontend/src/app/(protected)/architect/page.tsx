import { Metadata } from 'next';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetch } from '@/utils/server-prefetch';
import { getServerActiveProjectId } from '@/utils/server-active-project';
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

  const [factory, projectId] = await Promise.all([
    createServerApiFactory(),
    getServerActiveProjectId(),
  ]);
  const [initialSessions, initialEndpoints] = await Promise.all([
    prefetch(Capability.Architect.READ, () =>
      factory.getArchitectClient().getSessions()
    ),
    // Same `limit: 1` query as `useProjectNeedsEndpoint`. Without the project
    // cookie the API returns `[]`, which would read as "no endpoint" and stick
    // in the cache, so leave that case to the client.
    projectId
      ? prefetch(Capability.Endpoint.READ, async () => {
          const response = await factory
            .getEndpointsClient()
            .getEndpoints({ limit: 1 });
          return response.data || [];
        })
      : undefined,
  ]);

  return (
    <ArchitectClient
      initialSessions={initialSessions}
      initialEndpoints={initialEndpoints}
    />
  );
}
