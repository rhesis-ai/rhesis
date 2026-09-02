import { Metadata } from 'next';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { requireSession } from '@/utils/require-session';
import { hasServerCapability } from '@/utils/server-permissions';
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

  let initialEndpoints: Endpoint[] | undefined;
  let initialProjects: Project[] | undefined;

  if (await hasServerCapability(Capability.Playground.USE)) {
    try {
      const factory = await createServerApiFactory();
      const [endpointsResponse, projectsResponse] = await Promise.all([
        factory.getEndpointsClient().getEndpoints(LIST_PARAMS),
        factory.getProjectsClient().getProjects(LIST_PARAMS),
      ]);
      initialEndpoints = endpointsResponse.data;
      initialProjects = projectsResponse.data;
    } catch {
      // Fall back to the client fetch.
    }
  }

  return (
    <PlaygroundClient
      initialEndpoints={initialEndpoints}
      initialProjects={initialProjects}
    />
  );
}
