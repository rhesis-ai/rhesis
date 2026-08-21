import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import ProjectsClientWrapper from '../ProjectsClientWrapper';
import { ACTIVE_PROJECT_DELETE_BLOCKED } from '../../constants';
import type { Project } from '@/utils/api-client/interfaces/project';

const mockGetAllProjects = jest.fn();
const mockDeleteProject = jest.fn();
const mockRefreshActiveProjects = jest.fn();
const mockShow = jest.fn();
let mockActiveProject: Project | null = null;

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    refresh: jest.fn(),
  }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({
    activeProject: mockActiveProject,
    projects: [],
    loading: false,
    refresh: mockRefreshActiveProjects,
    syncProject: jest.fn(),
    setActiveProject: jest.fn(),
  }),
}));

jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({
    markStepComplete: jest.fn(),
    progress: { projectCreated: true },
    activeTour: null,
  }),
}));

jest.mock('@/hooks/useOnboardingTour', () => ({
  useOnboardingTour: jest.fn(),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow, close: jest.fn() }),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getProjectsClient: () => ({
      getAllProjects: mockGetAllProjects,
      deleteProject: mockDeleteProject,
      createProject: jest.fn(),
    }),
  })),
}));

jest.mock('@/components/layout/PageLayout', () => ({
  PageLayout: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock('../ProjectCreateDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('../ProjectFilterDrawer', () => ({
  __esModule: true,
  default: () => null,
  EMPTY_FILTERS: { activeStatus: null, environments: [] },
  hasActiveProjectFilters: () => false,
  countActiveProjectFilters: () => 0,
}));

jest.mock('@/components/common/DeleteModal', () => ({
  DeleteModal: ({
    open,
    onConfirm,
  }: {
    open: boolean;
    onConfirm: () => void;
  }) =>
    open ? (
      <div data-testid="delete-modal">
        <button onClick={onConfirm}>Confirm Delete</button>
      </div>
    ) : null,
}));

const ACTIVE = { id: 'proj-1', name: 'Regulatory Advisor' } as Project;
const OTHER = { id: 'proj-2', name: 'Example Project' } as Project;

function trashFor(name: string) {
  // The card root is a ButtonBase; the trash can lives inside it.
  const card = screen
    .getByText(name)
    .closest('.MuiButtonBase-root') as HTMLElement;
  return within(card).getByRole('button', { name: 'Delete project' });
}

async function renderList() {
  const { rerender } = render(<ProjectsClientWrapper />);
  await waitFor(() =>
    expect(screen.getByText('Regulatory Advisor')).toBeInTheDocument()
  );
  return { rerender: () => rerender(<ProjectsClientWrapper />) };
}

describe('ProjectsClientWrapper active-project delete guard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetAllProjects.mockResolvedValue([ACTIVE, OTHER]);
    mockDeleteProject.mockResolvedValue(undefined);
    mockRefreshActiveProjects.mockResolvedValue(undefined);
    mockActiveProject = ACTIVE;
  });

  it('disables the trash can on the active project only', async () => {
    await renderList();

    expect(trashFor('Regulatory Advisor')).toBeDisabled();
    expect(trashFor('Example Project')).toBeEnabled();
  });

  it('explains why the active project cannot be deleted', async () => {
    await renderList();

    const trash = trashFor('Regulatory Advisor');
    // Hover the span wrapper: the disabled button has pointer-events: none.
    await userEvent.hover(trash.parentElement as HTMLElement);

    expect(
      await screen.findByRole('tooltip', {
        name: ACTIVE_PROJECT_DELETE_BLOCKED,
      })
    ).toBeInTheDocument();
  });

  it('deletes a non-active project and refreshes the sidebar list', async () => {
    await renderList();

    await userEvent.click(trashFor('Example Project'));
    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    await waitFor(() =>
      expect(mockDeleteProject).toHaveBeenCalledWith('proj-2')
    );
    expect(mockRefreshActiveProjects).toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByText('Example Project')).not.toBeInTheDocument()
    );
  });

  it('refuses the delete when the target became the active project mid-flight', async () => {
    mockActiveProject = null;
    const { rerender } = await renderList();

    await userEvent.click(trashFor('Example Project'));
    // The active project resolves while the confirmation dialog is open — the
    // re-render is what a real context update would trigger.
    mockActiveProject = OTHER;
    rerender();

    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    await waitFor(() =>
      expect(screen.queryByTestId('delete-modal')).not.toBeInTheDocument()
    );
    expect(mockDeleteProject).not.toHaveBeenCalled();
    // The dialog must not just vanish with no explanation.
    expect(mockShow).toHaveBeenCalledWith(
      ACTIVE_PROJECT_DELETE_BLOCKED,
      expect.objectContaining({ severity: 'warning' })
    );
  });

  it('surfaces a failed delete instead of failing silently', async () => {
    mockDeleteProject.mockRejectedValue(new Error('Server error'));
    await renderList();

    await userEvent.click(trashFor('Example Project'));
    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    await waitFor(() =>
      expect(mockShow).toHaveBeenCalledWith(
        'Server error',
        expect.objectContaining({ severity: 'error' })
      )
    );
    expect(screen.getByText('Example Project')).toBeInTheDocument();
  });
});
