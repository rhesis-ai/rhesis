import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import TasksGrid from '../TasksGrid';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
  usePathname: () => '/tasks',
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok', user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn(), close: jest.fn() }),
  NotificationProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

const mockGetTasks = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTasksClient: () => ({ getTasks: mockGetTasks }),
  })),
}));

jest.mock('@/components/common/BaseDataGrid', () => {
  return function MockBaseDataGrid({
    rows,
    loading,
  }: {
    rows: Array<Record<string, unknown>>;
    loading?: boolean;
  }) {
    if (loading) return <div data-testid="grid-loading">Loading…</div>;
    return (
      <div data-testid="base-data-grid">
        {rows.map(row => (
          <div key={String(row.id)} data-testid={`row-${row.id}`} />
        ))}
      </div>
    );
  };
});

jest.mock('@/components/common/DeleteModal', () => ({
  DeleteModal: () => null,
}));

const makeTasksResponse = (
  data: Array<Record<string, unknown>>,
  total?: number
) => ({
  data,
  totalCount: total ?? data.length,
});

const makeTask = (id: string, title = 'Task') => ({
  id,
  title,
  status: { name: 'Open' },
});

describe('TasksGrid', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Default: one row, so tests that don't care about emptiness exercise the
    // populated (grid) branch rather than the empty-state branch.
    mockGetTasks.mockResolvedValue(makeTasksResponse([makeTask('t-0')]));
  });

  it('shows a loading state while the first fetch is in flight', () => {
    mockGetTasks.mockReturnValue(new Promise(() => {}));
    render(<TasksGrid canCreate onCreateClick={jest.fn()} />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByTestId('base-data-grid')).not.toBeInTheDocument();
  });

  it('renders the empty state directly, without ever mounting the grid, when there are zero tasks', async () => {
    mockGetTasks.mockResolvedValue(makeTasksResponse([]));
    render(<TasksGrid canCreate onCreateClick={jest.fn()} />);
    expect(await screen.findByText('No tasks yet')).toBeInTheDocument();
    expect(screen.queryByTestId('base-data-grid')).not.toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('renders the grid, not the empty state, when tasks exist', async () => {
    render(<TasksGrid canCreate onCreateClick={jest.fn()} />);
    expect(await screen.findByTestId('row-t-0')).toBeInTheDocument();
    expect(screen.queryByText('No tasks yet')).not.toBeInTheDocument();
  });

  it('shows the error alert instead of the empty state when the fetch fails', async () => {
    mockGetTasks.mockRejectedValue(new Error('Network error'));
    render(<TasksGrid canCreate onCreateClick={jest.fn()} />);
    expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    expect(screen.queryByText('No tasks yet')).not.toBeInTheDocument();
  });
});
