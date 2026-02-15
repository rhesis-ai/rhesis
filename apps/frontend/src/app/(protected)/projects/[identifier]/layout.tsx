import { Metadata } from 'next';
import { auth } from '@/auth';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

// Generate metadata for the page
export async function generateMetadata({
  params,
}: {
  params: Promise<{ identifier: string }>;
}): Promise<Metadata> {
  try {
    const resolvedParams = await params;
    const identifier = resolvedParams.identifier;
    const session = (await auth()) as { session_token: string } | null;

    // If no session (like during warmup), return basic metadata
    if (!session?.session_token) {
      return {
        title: `Project ${identifier}`,
        description: `Details for Project ${identifier}`,
      };
    }

    const apiFactory = new ApiClientFactory(session.session_token);
    const projectsClient = apiFactory.getProjectsClient();
    const project = await projectsClient.getProject(identifier);

    return {
      title: project.name || `Project ${identifier}`,
      description: `Project details for: ${project.name || identifier}`,
    };
  } catch (_error) {
    return {
      title: 'Project Details',
    };
  }
}

export default function ProjectDetailLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
