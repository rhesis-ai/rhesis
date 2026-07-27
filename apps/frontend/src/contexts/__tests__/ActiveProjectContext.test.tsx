import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  ActiveProjectProvider,
  useActiveProject,
} from '@/contexts/ActiveProjectContext';
import type { Project } from '@/utils/api-client/interfaces/project';

let mockSession: { data: unknown; status: string } = {
  data: null,
  status: 'unauthenticated',
};

jest.mock('next-auth/react', () => ({
  useSession: () => mockSession,
}));

jest.mock('next/navigation', () => ({
  usePathname: () => '/projects/proj-1',
}));

const getMyProjects = jest.fn();
jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getProjectsClient: () => ({ getMyProjects }),
  })),
}));

function Probe() {
  const { activeProject, projects, syncProject } = useActiveProject();

  return (
    <div>
      <span data-testid="active-name">{activeProject?.name ?? 'none'}</span>
      <span data-testid="project-list">
        {projects.map(p => p.name).join(',')}
      </span>
      <button
        type="button"
        onClick={() =>
          syncProject({
            id: 'proj-1',
            name: 'Renamed Project',
          } as Project)
        }
      >
        sync
      </button>
    </div>
  );
}

describe('ActiveProjectProvider.syncProject', () => {
  it('updates active project and project list without refetch', () => {
    const initialProject = {
      id: 'proj-1',
      name: 'Original Name',
    } as Project;

    render(
      <ActiveProjectProvider initialActiveProject={initialProject}>
        <Probe />
      </ActiveProjectProvider>
    );

    expect(screen.getByTestId('active-name')).toHaveTextContent(
      'Original Name'
    );
    expect(screen.getByTestId('project-list')).toHaveTextContent(
      'Original Name'
    );

    act(() => {
      screen.getByRole('button', { name: 'sync' }).click();
    });

    expect(screen.getByTestId('active-name')).toHaveTextContent(
      'Renamed Project'
    );
    expect(screen.getByTestId('project-list')).toHaveTextContent(
      'Renamed Project'
    );
  });

  it('upserts into the project list when the project was not cached', () => {
    function UpsertProbe() {
      const { projects, syncProject } = useActiveProject();

      return (
        <div>
          <span data-testid="project-list">
            {projects.map(p => p.name).join(',')}
          </span>
          <button
            type="button"
            onClick={() =>
              syncProject({
                id: 'proj-2',
                name: 'New Name',
              } as Project)
            }
          >
            sync
          </button>
        </div>
      );
    }

    render(
      <ActiveProjectProvider>
        <UpsertProbe />
      </ActiveProjectProvider>
    );

    expect(screen.getByTestId('project-list')).toHaveTextContent('');

    act(() => {
      screen.getByRole('button', { name: 'sync' }).click();
    });

    expect(screen.getByTestId('project-list')).toHaveTextContent('New Name');
  });
});

describe('ActiveProjectProvider server-seeded initial data', () => {
  beforeEach(() => {
    getMyProjects.mockClear();
    document.cookie = 'rh_active_project_id=; path=/; SameSite=Lax; max-age=0';
    mockSession = {
      data: {
        user: { id: 'user-1', organization_id: 'org-1' },
      },
      status: 'authenticated',
    };
  });

  afterEach(() => {
    mockSession = { data: null, status: 'unauthenticated' };
  });

  it('reuses the server-seeded project list instead of fetching /projects/mine', async () => {
    const seededProject = { id: 'proj-1', name: 'Seeded Project' } as Project;
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <ActiveProjectProvider
          initialActiveProject={seededProject}
          initialProjects={[seededProject]}
        >
          <Probe />
        </ActiveProjectProvider>
      </QueryClientProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('active-name')).toHaveTextContent(
        'Seeded Project'
      )
    );
    expect(getMyProjects).not.toHaveBeenCalled();
  });

  it('falls back to fetching /projects/mine when no initial data was seeded', async () => {
    getMyProjects.mockResolvedValue([{ id: 'proj-9', name: 'Fetched' }]);
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <ActiveProjectProvider>
          <Probe />
        </ActiveProjectProvider>
      </QueryClientProvider>
    );

    await waitFor(() => expect(getMyProjects).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(screen.getByTestId('active-name')).toHaveTextContent('Fetched')
    );
  });
});
