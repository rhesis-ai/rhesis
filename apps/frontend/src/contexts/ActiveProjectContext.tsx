'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { useSession } from 'next-auth/react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  clearActiveProjectId,
  readActiveProjectId,
  writeActiveProjectId,
} from '@/utils/active-project';
import { Project } from '@/utils/api-client/interfaces/project';

interface ActiveProjectContextValue {
  /** Projects the current user is a member of. */
  projects: Project[];
  /** The currently active project, or null if none selected. */
  activeProject: Project | null;
  /** Whether the project list is loading. */
  loading: boolean;
  /** Switch to a different project (or clear by passing null). */
  setActiveProject: (project: Project | null) => void;
  /** Reload the member-project list from the API. */
  refresh: () => Promise<void>;
}

const ActiveProjectContext = createContext<ActiveProjectContextValue>({
  projects: [],
  activeProject: null,
  loading: false,
  setActiveProject: () => {},
  refresh: async () => {},
});

export function ActiveProjectProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session } = useSession();
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProjectState] = useState<Project | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchProjects = useCallback(async () => {
    if (!session?.session_token) return;
    setLoading(true);
    try {
      const factory = new ApiClientFactory(session.session_token);
      const projectsClient = factory.getProjectsClient();
      const data = await projectsClient.getMyProjects();
      setProjects(data);

      // Selection precedence: cookie > user default_project > single project > none.

      // 1. Restore the cookie-persisted active project if it is still in the list.
      const stored = readActiveProjectId();
      if (stored) {
        const found = data.find(p => String(p.id) === stored) ?? null;
        if (found) {
          setActiveProjectState(found);
          return;
        }
        clearActiveProjectId();
      }

      // 2. Fall back to the user's configured default project.
      let defaultId: string | null = null;
      try {
        const settings = await factory.getUsersClient().getUserSettings();
        defaultId = settings?.default_project?.project_id
          ? String(settings.default_project.project_id)
          : null;
      } catch {
        // ignore — fall through to single-project auto-select
      }
      const defaultProject = defaultId
        ? (data.find(p => String(p.id) === defaultId) ?? null)
        : null;

      if (defaultProject) {
        writeActiveProjectId(String(defaultProject.id));
        setActiveProjectState(defaultProject);
      } else if (data.length === 1) {
        // 3. Auto-select when the user only belongs to one project.
        writeActiveProjectId(String(data[0].id));
        setActiveProjectState(data[0]);
      } else {
        // 4. Nothing selected.
        setActiveProjectState(null);
      }
    } catch {
      // silently ignore — the switcher will show an empty list
    } finally {
      setLoading(false);
    }
  }, [session?.session_token]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const setActiveProject = useCallback((project: Project | null) => {
    const previousId = readActiveProjectId();
    const nextId = project ? String(project.id) : null;

    if (project) {
      writeActiveProjectId(nextId as string);
    } else {
      clearActiveProjectId();
    }
    setActiveProjectState(project);

    // Project scope is sent as the X-Project-Id header, read from the cookie at
    // request time. Most data views are client components that fetch once on mount,
    // so router.refresh() (server-only) would not refetch them. A full reload is the
    // reliable way to make every project-scoped view pick up the new project.
    if (previousId !== nextId && typeof window !== 'undefined') {
      window.location.reload();
    }
  }, []);

  return (
    <ActiveProjectContext.Provider
      value={{
        projects,
        activeProject,
        loading,
        setActiveProject,
        refresh: fetchProjects,
      }}
    >
      {children}
    </ActiveProjectContext.Provider>
  );
}

export function useActiveProject(): ActiveProjectContextValue {
  return useContext(ActiveProjectContext);
}
