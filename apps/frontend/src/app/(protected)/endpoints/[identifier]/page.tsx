import * as React from 'react';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import EndpointDetailPageClient, {
  isValidEndpointId,
} from './components/EndpointDetailPageClient';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import type { Project } from '@/utils/api-client/interfaces/project';

interface PageProps {
  params: Promise<{ identifier: string }>;
}

export default async function EndpointPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const { identifier } = await params;

  // A malformed id is reported by the client, the same way it was before.
  if (!isValidEndpointId(identifier)) {
    return <EndpointDetailPageClient identifier={identifier} />;
  }

  const factory = await createServerApiFactory();

  let endpoint: Endpoint;
  try {
    endpoint = await factory.getEndpointsClient().getEndpoint(identifier);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  // The project only feeds breadcrumbs, so a failure here falls back to the
  // client fetch instead of failing the page.
  let project: Project | undefined;
  if (endpoint.project_id) {
    try {
      project = await factory
        .getProjectsClient()
        .getProject(endpoint.project_id);
    } catch {
      project = undefined;
    }
  }

  return (
    <EndpointDetailPageClient
      identifier={identifier}
      initialEndpoint={JSON.parse(JSON.stringify(endpoint))}
      initialProject={project ? JSON.parse(JSON.stringify(project)) : undefined}
    />
  );
}
