import { auth } from '@/auth';
import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { getServerActiveProjectId } from '@/utils/server-active-project';
import { type Project } from '@/utils/api-client/interfaces/project';
import ProtectedLayoutClient from './ProtectedLayoutClient';

export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth().catch(() => null);
  const projectId = await getServerActiveProjectId();

  let initialActiveProject: Project | null = null;
  if (projectId && session?.session_token) {
    try {
      const factory = await createServerApiFactory(session.session_token);
      initialActiveProject = await factory
        .getProjectsClient()
        .getProject(projectId);
    } catch {
      // Ignore — client will fetch on mount and populate the provider
    }
  }

  return (
    <ProtectedLayoutClient initialActiveProject={initialActiveProject}>
      {children}
    </ProtectedLayoutClient>
  );
}
