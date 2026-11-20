export const dynamic = 'force-dynamic';

import { createServerApiFactory } from '@/utils/api-client/server-factory';
import { prefetch } from '@/utils/server-prefetch';
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

  const initialData = await prefetch<Project[]>(
    Capability.Project.READ,
    async () =>
      (await createServerApiFactory()).getProjectsClient().getAllProjects({
        sort_by: 'name',
        sort_order: 'asc',
      })
  );

  return <ProjectsClientWrapper initialData={initialData} />;
}
