import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import ClientWrapper from './client-wrapper';

interface PageProps {
  params: Promise<{ identifier: string }>;
  searchParams?: Promise<Record<string, string | string[]>>;
}

export default async function ProjectDetailPage({ params }: PageProps) {
  const session = await auth();

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  const apiFactory = new ApiClientFactory(session.session_token);
  const projectsClient = apiFactory.getProjectsClient();
  const resolvedParams = await params;
  const project = await projectsClient.getProject(resolvedParams.identifier);

  return (
    <ClientWrapper
      project={project}
      sessionToken={session.session_token}
      projectId={project.id}
    />
  );
}
