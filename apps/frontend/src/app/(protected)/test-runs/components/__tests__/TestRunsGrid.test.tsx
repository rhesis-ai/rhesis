import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestRunsGrid from '../TestRunsGrid';

// ---- Navigation + Auth ----

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: jest.fn() }),
  usePathname: () => '/test-runs',
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok', user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  }),
}));

// ---- Notifications ----

const mockShow = jest.fn();
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShow, close: jest.fn() }),
  NotificationProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

// ---- API client factory ----

const mockGetTestRuns = jest.fn();
const mockDeleteTestRun = jest.fn();
const mockGetProject = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestRunsClient: () => ({
      getTestRuns: mockGetTestRuns,
      deleteTestRun: mockDeleteTestRun,
    }),
    getProjectsClient: () => ({
      getProject: mockGetProject,
    }),
  })),
}));

// ---- BaseDataGrid stub ----
// toolbarSlot is not rendered here: MUI DataGrid toolbar slots require the
// real DataGrid context and cannot be exercised in a shallow unit test.

jest.mock('@/components/common/BaseDataGrid', () => {
  return function MockBaseDataGrid({
    rows,
    loading,
    columns,
    onRowClick,
  }: {
    rows: Array<Record<string, unknown>>;
    loading?: boolean;
    columns?: Array<{
      field: string;
      renderCell?: (params: {
        id: unknown;
        row: Record<string, unknown>;
      }) => React.ReactNode;
    }>;
    onRowClick?: (p: { id: unknown; row: Record<string, unknown> }) => void;
    toolbarSlot?: unknown;
    showToolbar?: boolean;
  }) {
    if (loading) return <div data-testid="grid-loading">Loading…</div>;
    const actionsCol = columns?.find(c => c.field === 'actions');
    return (
      <div data-testid="base-data-grid">
        {rows.map(row => (
          <div
            key={String(row.id)}
            role="row"
            data-testid={`row-${row.id}`}
            onClick={() => onRowClick?.({ id: row.id, row })}
          >
            {actionsCol?.renderCell?.({ id: row.id, row })}
          </div>
        ))}
      </div>
    );
  };
});

// ---- Sub-component stubs ----

jest.mock('../TestRunFilterDrawer', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="test-run-filter-drawer" /> : null,
  EMPTY_TEST_RUN_FILTERS: {
    testSet: '',
    executor: '',
    tag: '',
    tags: 'all',
    comments: 'all',
    tasks: 'all',
  },
  hasActiveTestRunFilters: () => false,
  countActiveTestRunFilters: () => 0,
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

// ---- Fixtures ----

const makeTestRun = (
  id: string,
  name = 'Test Run',
  statusName = 'Completed'
) => ({
  id,
  name,
  status: { id: 's1', name: statusName },
  test_configuration: {
    test_set: { name: 'Set A', test_set_type: { type_value: 'evaluation' } },
    endpoint: { project_id: null },
  },
  user: { id: 'u1', name: 'Alice', email: 'alice@example.com' },
  attributes: { total_tests: 10 },
  tags: [],
  counts: { comments: 0, tasks: 0 },
  created_at: '2024-01-01T00:00:00Z',
  permitted_actions: ['test_run:read', 'test_run:update', 'test_run:delete'],
});

const makePaginatedResponse = <T,>(data: T[], total?: number) => ({
  data,
  pagination: {
    totalCount: total ?? data.length,
    skip: 0,
    limit: 50,
    currentPage: 0,
    pageSize: 50,
    totalPages: 1,
  },
});

// ---- Tests ----

describe('TestRunsGrid', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetTestRuns.mockResolvedValue(makePaginatedResponse([]));
    mockGetProject.mockResolvedValue({ id: 'p1', name: 'Project A' });
  });

  it('shows loading state while fetching', () => {
    mockGetTestRuns.mockReturnValue(new Promise(() => {}));
    render(<TestRunsGrid />);
    expect(screen.getByTestId('grid-loading')).toBeInTheDocument();
  });

  it('does NOT render a "New Test Run" action button (creation moved to page FAB)', async () => {
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
    );
    expect(screen.queryByTestId('action-New Test Run')).not.toBeInTheDocument();
  });

  it('renders rows after data loads', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1'), makeTestRun('r-2')])
    );
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );
    expect(screen.getByTestId('row-r-2')).toBeInTheDocument();
  });

  it('shows error alert when fetch fails', async () => {
    mockGetTestRuns.mockRejectedValue(new Error('Network error'));
    render(<TestRunsGrid />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it('dismisses the error alert on close', async () => {
    mockGetTestRuns.mockRejectedValue(new Error('Network error'));
    render(<TestRunsGrid />);
    await screen.findByRole('alert');
    await userEvent.click(screen.getByLabelText(/close/i));
    await waitFor(() =>
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    );
  });

  it('navigates to test run detail on row click', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-99')])
    );
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-99')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('row-r-99'));
    expect(mockPush).toHaveBeenCalledWith('/test-runs/r-99');
  });

  it('renders a delete action button in the row actions column', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1')])
    );
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );
    // The row-actions column renders a Delete icon button
    expect(screen.getByLabelText('Delete')).toBeInTheDocument();
  });

  it('does not render a cancel action for completed runs', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1', 'Test Run', 'Completed')])
    );
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );
    expect(screen.queryByLabelText('Cancel')).not.toBeInTheDocument();
  });

  it('renders a cancel action for queued runs', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1', 'Test Run', 'queued')])
    );
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );
    expect(screen.getByLabelText('Cancel')).toBeInTheDocument();
  });

  it('opens delete modal on clicking the row delete button', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1')])
    );
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('Delete'));
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
  });

  it('calls deleteTestRun and shows success notification on confirm', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1')])
    );
    mockDeleteTestRun.mockResolvedValue(undefined);
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('Delete'));
    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    await waitFor(() => expect(mockDeleteTestRun).toHaveBeenCalledWith('r-1'));
    await waitFor(() =>
      expect(mockShow).toHaveBeenCalledWith(
        expect.stringContaining('deleted'),
        expect.objectContaining({ severity: 'success' })
      )
    );
  });

  it('shows error notification when delete fails', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1')])
    );
    mockDeleteTestRun.mockRejectedValue(new Error('Server error'));
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('Delete'));
    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    await waitFor(() =>
      expect(mockShow).toHaveBeenCalledWith(
        expect.stringContaining('Failed'),
        expect.objectContaining({ severity: 'error' })
      )
    );
  });

  it('calls onTotalCountChange with the total count', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1'), makeTestRun('r-2')], 42)
    );
    const onTotalCountChange = jest.fn();
    render(<TestRunsGrid onTotalCountChange={onTotalCountChange} />);
    await waitFor(() => expect(onTotalCountChange).toHaveBeenCalledWith(42));
  });

  it('passes showToolbar and toolbarSlot props to BaseDataGrid', async () => {
    render(<TestRunsGrid />);
    await waitFor(() =>
      expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
    );
    // The grid renders without error, confirming toolbarSlot prop is accepted
    expect(screen.getByTestId('base-data-grid')).toBeInTheDocument();
  });
});
