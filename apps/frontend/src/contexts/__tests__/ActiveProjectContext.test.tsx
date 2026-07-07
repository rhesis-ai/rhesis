import React from 'react';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import {
  ActiveProjectProvider,
  useActiveProject,
} from '@/contexts/ActiveProjectContext';
import type { Project } from '@/utils/api-client/interfaces/project';

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null }),
}));

jest.mock('next/navigation', () => ({
  usePathname: () => '/projects/proj-1',
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn(),
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
