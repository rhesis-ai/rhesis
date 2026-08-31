export const dynamic = 'force-dynamic';

import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { hasServerCapability } from '@/utils/server-permissions';
import { Capability } from '@/constants/capabilities';
import type { Project } from '@/utils/api-client/interfaces/project';
import ProjectsClientWrapper from './components/ProjectsClientWrapper';
import { requireSession } from '@/utils/require-session';

/**
 * Server component for the Projects page. Prefetches the project list so the
 * first paint has content; on permission denial or fetch failure it passes
 * `undefined` and the client wrapper falls back to fetching on mount.
 */
export default async function ProjectsPage() {
  await requireSession();

  let initialData: Project[] | undefined;
  if (await hasServerCapability(Capability.Project.READ)) {
    try {
      const factory = await createServerApiFactory();
      const data = await factory.getProjectsClient().getAllProjects({
        sort_by: 'name',
        sort_order: 'asc',
      });
      initialData = JSON.parse(JSON.stringify(data));
    } catch (error) {
      console.error('Failed to prefetch projects:', error);
    }
  }

  return <ProjectsClientWrapper initialData={initialData} />;
}
