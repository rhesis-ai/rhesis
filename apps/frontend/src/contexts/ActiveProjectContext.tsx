'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useSession } from 'next-auth/react';
import { usePathname } from 'next/navigation';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  clearActiveProjectId,
  readActiveProjectId,
  writeActiveProjectId,
} from '@/utils/active-project';
import type { UUID } from 'crypto';
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
  refresh: (options?: { listOnly?: boolean }) => Promise<void>;
  /** Update cached project data after an in-place edit (no reload). */
  syncProject: (project: Project) => void;
}

const ActiveProjectContext = createContext<ActiveProjectContextValue>({
  projects: [],
  activeProject: null,
  loading: false,
  setActiveProject: () => {},
  refresh: async () => {},
  syncProject: () => {},
});

export function ActiveProjectProvider({
  children,
  initialActiveProject = null,
}: {
  children: React.ReactNode;
  initialActiveProject?: Project | null;
}) {
  const { data: session } = useSession();
  const pathname = usePathname();
  const pathnameRef = useRef(pathname);
  pathnameRef.current = pathname;
  const [projects, setProjects] = useState<Project[]>(
    initialActiveProject ? [initialActiveProject] : []
  );
  const [activeProject, setActiveProjectState] = useState<Project | null>(
    initialActiveProject
  );
  const [loading, setLoading] = useState(true);

  const fetchProjects = useCallback(
    async (options?: { listOnly?: boolean }) => {
      if (!session?.session_token) return;
      if (pathnameRef.current.startsWith('/onboarding')) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const factory = new ApiClientFactory(session.session_token);
        const projectsClient = factory.getProjectsClient();
        const data = await projectsClient.getMyProjects();
        setProjects(data);

        if (options?.listOnly) {
          // Keep the current selection when it still exists; drop it if removed.
          setActiveProjectState(prev => {
            if (!prev) {
              if (data.length === 1) {
                writeActiveProjectId(String(data[0].id));
                return data[0];
              }
              return null;
            }
            const stillMember =
              data.find(p => String(p.id) === String(prev.id)) ?? null;
            if (stillMember) return stillMember;
            clearActiveProjectId();
            return null;
          });
          return;
        }

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
    },
    [session?.session_token]
  );

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const setActiveProject = useCallback(
    async (project: Project | null) => {
      const previousId = readActiveProjectId();
      const nextId = project ? String(project.id) : null;

      if (project) {
        writeActiveProjectId(nextId as string);

        // Persist as default_project so the selection survives logout/login.
        const token = session?.session_token;
        if (token) {
          try {
            const factory = new ApiClientFactory(token);
            await factory.getUsersClient().updateUserSettings({
              default_project: {
                project_id: project.id as UUID,
                name: project.name,
              },
            });
          } catch {
            // Cookie still scopes the current session; ignore persistence failure.
          }
        }
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
    },
    [session?.session_token]
  );

  const refresh = useCallback(
    (options?: { listOnly?: boolean }) =>
      fetchProjects({ listOnly: options?.listOnly ?? true }),
    [fetchProjects]
  );

  const syncProject = useCallback((project: Project) => {
    const id = String(project.id);
    setProjects(prev => {
      const exists = prev.some(p => String(p.id) === id);
      if (!exists) return [...prev, project];
      return prev.map(p => (String(p.id) === id ? { ...p, ...project } : p));
    });
    setActiveProjectState(prev =>
      prev && String(prev.id) === id ? { ...prev, ...project } : prev
    );
  }, []);

  return (
    <ActiveProjectContext.Provider
      value={{
        projects,
        activeProject,
        loading,
        setActiveProject,
        refresh,
        syncProject,
      }}
    >
      {children}
    </ActiveProjectContext.Provider>
  );
}

export function useActiveProject(): ActiveProjectContextValue {
  return useContext(ActiveProjectContext);
}
