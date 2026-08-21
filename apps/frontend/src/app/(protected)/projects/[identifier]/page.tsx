import { notFound } from 'next/navigation';
import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { isNotFoundApiError } from '@/utils/api-client/is-not-found-error';
import type { Project } from '@/utils/api-client/interfaces/project';
import ClientWrapper from './client-wrapper';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams?: Promise<Record<string, string | string[]>>;
}

export default async function ProjectDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session || session.error) {
    throw new Error('No session token available');
  }

  const apiFactory = await createServerApiFactory();
  const projectsClient = apiFactory.getProjectsClient();
  const resolvedParams = await params;

  let project: Project;
  try {
    project = await projectsClient.getProject(resolvedParams.identifier);
  } catch (error) {
    // Projects deviate from the repo's 404-only notFoundIfEntityMissing pattern on
    // purpose. A deleted project comes back as 410 with a restore offer, but deleting
    // a project hard-drops every project_membership row and restoring does not
    // re-enroll anyone — so a restored project would be invisible to everyone. Treat
    // gone and missing the same way.
    if (isNotFoundApiError(error)) notFound();
    throw error;
  }

  return <ClientWrapper project={project} projectId={project.id} />;
}
