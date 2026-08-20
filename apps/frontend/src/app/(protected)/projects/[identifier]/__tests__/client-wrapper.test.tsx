import React from 'react';
import { render, screen, waitFor, within } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import ClientWrapper from '../client-wrapper';
import type { Project } from '@/utils/api-client/interfaces/project';
import { ACTIVE_PROJECT_DELETE_BLOCKED } from '../../constants';

const mockReplace = jest.fn();
const mockDeleteProject = jest.fn();
const mockShow = jest.fn();
const mockSyncProject = jest.fn();
const mockRefreshActiveProjects = jest.fn();
let mockActiveProject: Project | null = null;

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: mockReplace,
    refresh: jest.fn(),
  }),
  useParams: () => ({ identifier: 'my-project' }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/projects/my-project',
}));

// ClientWrapper now invalidates the cached /usage response after deleting a
// project (a stock resource), and that path reads the session for its query
// scope. `status` is required alongside `data` -- see apps/frontend/AGENTS.md.
jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/hooks/useOnboardingTour', () => ({
  useOnboardingTour: jest.fn(),
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({
    syncProject: mockSyncProject,
    activeProject: mockActiveProject,
    projects: [],
    refresh: mockRefreshActiveProjects,
  }),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow, close: jest.fn() }),
  NotificationProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getProjectsClient: () => ({
      deleteProject: mockDeleteProject,
      updateProject: jest.fn(),
    }),
  })),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/components/layout/PageLayout', () => ({
  PageLayout: ({
    children,
    actions,
  }: {
    children: React.ReactNode;
    actions?: React.ReactNode;
  }) => (
    <div>
      <div data-testid="page-actions">{actions}</div>
      {children}
    </div>
  ),
}));

jest.mock('../components/ProjectDetailTabs', () => ({
  __esModule: true,
  default: () => <div data-testid="project-detail-tabs" />,
}));

jest.mock('../edit-drawer', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('@/components/common/DeleteModal', () => ({
  DeleteModal: ({
    open,
    onConfirm,
    onClose,
    isLoading,
  }: {
    open: boolean;
    onConfirm: () => void;
    onClose: () => void;
    isLoading?: boolean;
  }) =>
    open ? (
      <div data-testid="delete-modal">
        <button onClick={onConfirm} disabled={isLoading}>
          Confirm Delete
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    ) : null,
}));

const makeProject = (): Project =>
  ({
    id: 'proj-1',
    name: 'My Project',
    description: 'A test project',
    created_at: '2024-01-15T00:00:00Z',
    owner: { id: 'user-1', name: 'Alice', email: 'alice@example.com' },
  }) as Project;

function deleteFab() {
  return within(screen.getByTestId('page-actions')).getByRole('button', {
    name: 'Delete project',
  });
}

function editFab() {
  return within(screen.getByTestId('page-actions')).getByRole('button', {
    name: 'Edit project',
  });
}

async function openDeleteModal() {
  await userEvent.click(deleteFab());
  expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
}

describe('Project detail ClientWrapper delete flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDeleteProject.mockResolvedValue(undefined);
    mockRefreshActiveProjects.mockResolvedValue(undefined);
    mockActiveProject = null;
  });

  it('closes the delete modal after a successful delete', async () => {
    render(<ClientWrapper project={makeProject()} projectId="proj-1" />);

    await openDeleteModal();
    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    await waitFor(() =>
      expect(mockDeleteProject).toHaveBeenCalledWith('proj-1')
    );
    await waitFor(() =>
      expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument()
    );
    expect(mockRefreshActiveProjects).toHaveBeenCalled();
    expect(mockReplace).toHaveBeenCalledWith('/projects');
    expect(mockShow).toHaveBeenCalledWith(
      'Project deleted successfully',
      expect.objectContaining({ severity: 'success' })
    );
  });

  it('unmounts the detail body once the project is gone', async () => {
    render(<ClientWrapper project={makeProject()} projectId="proj-1" />);
    expect(screen.getByTestId('project-detail-tabs')).toBeInTheDocument();

    await openDeleteModal();
    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    // The empty detail shell must never be shown between the DELETE and the
    // navigation landing.
    await waitFor(() =>
      expect(
        screen.queryByTestId('project-detail-tabs')
      ).not.toBeInTheDocument()
    );
  });

  it('closes the delete modal when deletion fails', async () => {
    mockDeleteProject.mockRejectedValue(new Error('Server error'));

    render(<ClientWrapper project={makeProject()} projectId="proj-1" />);

    await openDeleteModal();
    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    await waitFor(() =>
      expect(mockShow).toHaveBeenCalledWith(
        'Server error',
        expect.objectContaining({ severity: 'error' })
      )
    );
    await waitFor(() =>
      expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument()
    );
    expect(mockReplace).not.toHaveBeenCalled();
    expect(screen.getByTestId('project-detail-tabs')).toBeInTheDocument();
  });
});

describe('Project detail ClientWrapper active-project guard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDeleteProject.mockResolvedValue(undefined);
    mockRefreshActiveProjects.mockResolvedValue(undefined);
    mockActiveProject = null;
  });

  it('disables delete with a reason when viewing the active project', async () => {
    mockActiveProject = { id: 'proj-1', name: 'My Project' } as Project;

    render(<ClientWrapper project={makeProject()} projectId="proj-1" />);

    const fab = deleteFab();
    expect(fab).toBeDisabled();

    // Hover the span wrapper: the disabled button itself has pointer-events: none.
    await userEvent.hover(fab.parentElement as HTMLElement);
    expect(
      await screen.findByRole('tooltip', {
        name: ACTIVE_PROJECT_DELETE_BLOCKED,
      })
    ).toBeInTheDocument();
  });

  it('leaves delete enabled when a different project is active', () => {
    mockActiveProject = { id: 'proj-2', name: 'Other Project' } as Project;

    render(<ClientWrapper project={makeProject()} projectId="proj-1" />);

    expect(deleteFab()).toBeEnabled();
  });

  it('keeps edit available on the active project', () => {
    mockActiveProject = { id: 'proj-1', name: 'My Project' } as Project;

    render(<ClientWrapper project={makeProject()} projectId="proj-1" />);

    expect(editFab()).toBeEnabled();
  });

  it('refuses the delete when the project became active while the dialog was open', async () => {
    // No active-project cookie yet, so the FAB renders enabled.
    mockActiveProject = null;
    const { rerender } = render(
      <ClientWrapper project={makeProject()} projectId="proj-1" />
    );

    await openDeleteModal();

    // ActiveProjectContext resolves and auto-selects this project.
    mockActiveProject = { id: 'proj-1', name: 'My Project' } as Project;
    rerender(<ClientWrapper project={makeProject()} projectId="proj-1" />);

    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    expect(mockDeleteProject).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument()
    );
    // The dialog must not just vanish with no explanation.
    expect(mockShow).toHaveBeenCalledWith(
      ACTIVE_PROJECT_DELETE_BLOCKED,
      expect.objectContaining({ severity: 'warning' })
    );
  });
});
