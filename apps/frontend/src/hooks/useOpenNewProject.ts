'use client';

import { useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { writeActiveProjectId } from '@/utils/active-project';
import type { Project } from '@/utils/api-client/interfaces/project';

/**
 * After creating a project: make it the active one and open it. Every create
 * path uses this so they all land in the same place. Not `setActiveProject`,
 * which reloads the current page instead of navigating.
 */
export function useOpenNewProject() {
  const router = useRouter();
  const { refresh } = useActiveProject();

  return useCallback(
    async (project: Pick<Project, 'id'>) => {
      writeActiveProjectId(String(project.id));
      await refresh({ listOnly: false });
      router.push(`/projects/${project.id}`);
    },
    [refresh, router]
  );
}
