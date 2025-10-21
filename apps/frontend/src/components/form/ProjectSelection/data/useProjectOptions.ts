'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Project } from '@/utils/api-client/interfaces/project';
import type { ProjectOption } from '../ProjectSelection.ui';

export type UseProjectOptionsResult = {
  readonly loading: boolean;
  readonly options: readonly ProjectOption[];
  readonly error?: string | null;
};

/**
 * Data selector to get the required information for the select box
 * @param p
 */
function mapProjectToOption(p: Project): ProjectOption {
  return {
    id: String(p.id),
    name: p.name ?? 'Unnamed Project',
    description: p.description ?? null,
    icon: p.icon ?? null,
  };
}

/**
 * data selector for project options
 * drop it later in favor of an easier client side state handling framework
 */
export function useProjectOptions(): UseProjectOptionsResult {
  const { data: session } = useSession();
  const [loading, setLoading] = React.useState<boolean>(true);
  const [error, setError] = React.useState<string | null>(null);
  const [options, setOptions] = React.useState<ProjectOption[]>([]);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const sessionToken = session?.session_token ?? '';
      if (!sessionToken) {
        setOptions([]);
        return;
      }

      const client = new ApiClientFactory(sessionToken).getProjectsClient();
      const response = await client.getProjects();
      const projectsArray: Project[] = Array.isArray(response)
        ? response
        : (response?.data ?? []);

      const opts = (projectsArray ?? []).map(mapProjectToOption);

      setOptions(opts);
    } catch (e) {
      setError((e as Error).message ?? 'Failed to load projects');
      setOptions([]);
    } finally {
      setLoading(false);
    }
  }, [session?.session_token]);

  React.useEffect(() => {
    if (!session) return;
    void load();
  }, [session, load]);

  return { loading, options, error };
}
