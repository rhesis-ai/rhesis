import * as React from 'react';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { notFoundIfEntityMissing } from '@/utils/entity-not-found-server';
import { isValidEndpointId } from '@/utils/is-valid-endpoint-id';
import ProjectEndpointDetailPageClient from './components/ProjectEndpointDetailPageClient';
import type { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import type { Project } from '@/utils/api-client/interfaces/project';

interface PageProps {
  params: Promise<{ identifier: string; endpointId: string }>;
}

export default async function ProjectEndpointPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('Authentication required');
  }

  const { identifier, endpointId } = await params;

  // A malformed id is reported by the client, the same way it was before.
  if (!isValidEndpointId(endpointId)) {
    return (
      <ProjectEndpointDetailPageClient
        projectId={identifier}
        endpointId={endpointId}
      />
    );
  }

  const factory = await createServerApiFactory();

  let endpoint: Endpoint;
  try {
    endpoint = await factory.getEndpointsClient().getEndpoint(endpointId);
  } catch (error) {
    notFoundIfEntityMissing(error);
    throw error;
  }

  // The project only feeds breadcrumbs, so a failure here falls back to the
  // client fetch instead of failing the page.
  let project: Project | undefined;
  try {
    project = await factory.getProjectsClient().getProject(identifier);
  } catch {
    project = undefined;
  }

  return (
    <ProjectEndpointDetailPageClient
      projectId={identifier}
      endpointId={endpointId}
      initialEndpoint={JSON.parse(JSON.stringify(endpoint))}
      initialProject={project ? JSON.parse(JSON.stringify(project)) : undefined}
    />
  );
}
