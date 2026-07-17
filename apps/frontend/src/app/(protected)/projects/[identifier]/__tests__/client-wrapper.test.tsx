import React from 'react';
import { render, screen, waitFor, within } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import ClientWrapper from '../client-wrapper';
import type { Project } from '@/utils/api-client/interfaces/project';

const mockPush = jest.fn();
const mockDeleteProject = jest.fn();
const mockShow = jest.fn();
const mockSyncProject = jest.fn();

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: jest.fn() }),
  useParams: () => ({ identifier: 'my-project' }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/projects/my-project',
}));

jest.mock('@/hooks/useOnboardingTour', () => ({
  useOnboardingTour: jest.fn(),
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({ syncProject: mockSyncProject }),
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
    user: { id: 'user-1', name: 'Alice', email: 'alice@example.com' },
    organization: { id: 'org-1', name: 'Acme' },
  }) as Project;

async function openDeleteModal() {
  const actions = screen.getByTestId('page-actions');
  const fabButtons = within(actions).getAllByRole('button');
  await userEvent.click(fabButtons[1]);
  expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
}

describe('Project detail ClientWrapper delete flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockDeleteProject.mockResolvedValue(undefined);
  });

  it('closes the delete modal after a successful delete', async () => {
    render(
      <ClientWrapper
        project={makeProject()}

        projectId="proj-1"
      />
    );

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
    expect(mockPush).toHaveBeenCalledWith('/projects');
    expect(mockShow).toHaveBeenCalledWith(
      'Project deleted successfully',
      expect.objectContaining({ severity: 'success' })
    );
  });

  it('closes the delete modal when deletion fails', async () => {
    mockDeleteProject.mockRejectedValue(new Error('Server error'));

    render(
      <ClientWrapper
        project={makeProject()}

        projectId="proj-1"
      />
    );

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
    expect(mockPush).not.toHaveBeenCalled();
  });
});
