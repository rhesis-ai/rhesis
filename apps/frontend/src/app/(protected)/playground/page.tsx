import { Metadata } from 'next';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { prefetch } from '@/utils/server-prefetch';
import { Capability } from '@/constants/capabilities';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { Project } from '@/utils/api-client/interfaces/project';
import PlaygroundClient from './components/PlaygroundClient';

export const metadata: Metadata = {
  title: 'Playground',
};

const LIST_PARAMS = {
  sort_by: 'name',
  sort_order: 'asc' as const,
  limit: 100,
};

/**
 * Server component: prefetches the endpoint/project lists the endpoint
 * picker needs so they're already in the query cache on first paint --
 * no client-side spinner while the dropdown itself loads. Fails open to
 * "no initial data" so the client falls back to its own fetch.
 */
export default async function PlaygroundPage() {
  await requireSession();

  const lists = await prefetch(Capability.Playground.USE, async () => {
    const factory = await createServerApiFactory();
    const [endpointsResponse, projectsResponse] = await Promise.all([
      factory.getEndpointsClient().getEndpoints(LIST_PARAMS),
      factory.getProjectsClient().getProjects(LIST_PARAMS),
    ]);
    return {
      endpoints: endpointsResponse.data as Endpoint[],
      projects: projectsResponse.data as Project[],
    };
  });

  return (
    <PlaygroundClient
      initialEndpoints={lists?.endpoints}
      initialProjects={lists?.projects}
    />
  );
}
