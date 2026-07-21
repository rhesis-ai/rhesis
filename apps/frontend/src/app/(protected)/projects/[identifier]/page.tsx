import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
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
  const project = await projectsClient.getProject(resolvedParams.identifier);

  return <ClientWrapper project={project} projectId={project.id} />;
}
