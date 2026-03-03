import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestRunsTable from '../TestRunsGrid';

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

type ActionButton = {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
};

jest.mock('@/components/common/BaseDataGrid', () => {
  return function MockBaseDataGrid({
    rows,
    loading,
    actionButtons,
    onRowClick,
    checkboxSelection,
    onRowSelectionModelChange,
    rowSelectionModel,
  }: {
    rows: Array<Record<string, unknown>>;
    loading?: boolean;
    actionButtons?: ActionButton[];
    onRowClick?: (p: { id: unknown; row: Record<string, unknown> }) => void;
    checkboxSelection?: boolean;
    onRowSelectionModelChange?: (sel: unknown[]) => void;
    rowSelectionModel?: unknown[];
  }) {
    if (loading) return <div data-testid="grid-loading">Loading…</div>;
    return (
      <div data-testid="base-data-grid">
        {actionButtons?.map(btn => (
          <button
            key={btn.label}
            onClick={btn.onClick}
            disabled={btn.disabled}
            data-testid={`action-${btn.label}`}
          >
            {btn.label}
          </button>
        ))}
        {rows.map(row => (
          <div
            key={String(row.id)}
            role="row"
            data-testid={`row-${row.id}`}
            onClick={() => onRowClick?.({ id: row.id, row })}
          >
            {checkboxSelection && (
              <input
                type="checkbox"
                aria-label={`select-${row.id}`}
                checked={((rowSelectionModel as unknown[]) ?? []).includes(
                  row.id
                )}
                onChange={e => {
                  const prev = (rowSelectionModel as unknown[]) ?? [];
                  onRowSelectionModelChange?.(
                    e.target.checked
                      ? [...prev, row.id]
                      : prev.filter(id => id !== row.id)
                  );
                }}
              />
            )}
          </div>
        ))}
      </div>
    );
  };
});

// ---- Sub-component stubs ----

jest.mock('../TestRunDrawer', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="test-run-drawer" /> : null,
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

const makeTestRun = (id: string, name = 'Test Run') => ({
  id,
  name,
  status: { id: 's1', name: 'Completed' },
  test_configuration: {
    test_set: { name: 'Set A', test_set_type: { type_value: 'evaluation' } },
    endpoint: { project_id: null },
  },
  user: { id: 'u1', name: 'Alice', email: 'alice@example.com' },
  attributes: { total_tests: 10 },
  tags: [],
  counts: { comments: 0, tasks: 0 },
  created_at: '2024-01-01T00:00:00Z',
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

describe('TestRunsTable', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetTestRuns.mockResolvedValue(makePaginatedResponse([]));
    mockGetProject.mockResolvedValue({ id: 'p1', name: 'Project A' });
  });

  it('shows loading state while fetching', () => {
    mockGetTestRuns.mockReturnValue(new Promise(() => {}));
    render(<TestRunsTable sessionToken="tok" />);
    expect(screen.getByTestId('grid-loading')).toBeInTheDocument();
  });

  it('renders "New Test Run" action button', async () => {
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
    );
    expect(screen.getByTestId('action-New Test Run')).toBeInTheDocument();
  });

  it('renders rows after data loads', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1'), makeTestRun('r-2')])
    );
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );
    expect(screen.getByTestId('row-r-2')).toBeInTheDocument();
  });

  it('shows error alert when fetch fails', async () => {
    mockGetTestRuns.mockRejectedValue(new Error('Network error'));
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText(/failed to load test runs/i)).toBeInTheDocument();
  });

  it('navigates to test run detail on row click', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-99')])
    );
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-99')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('row-r-99'));
    expect(mockPush).toHaveBeenCalledWith('/test-runs/r-99');
  });

  it('shows "Delete Test Runs" button when rows are selected', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1')])
    );
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('select-r-1'));
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Test Runs')).toBeInTheDocument()
    );
  });

  it('hides "Delete Test Runs" button when nothing is selected', async () => {
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
    );
    expect(
      screen.queryByTestId('action-Delete Test Runs')
    ).not.toBeInTheDocument();
  });

  it('opens delete modal on clicking "Delete Test Runs"', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1')])
    );
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('select-r-1'));
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Test Runs')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-Delete Test Runs'));
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
  });

  it('calls deleteTestRun and shows success notification on confirm', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1')])
    );
    mockDeleteTestRun.mockResolvedValue(undefined);
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('select-r-1'));
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Test Runs')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-Delete Test Runs'));
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
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-r-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('select-r-1'));
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Test Runs')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-Delete Test Runs'));
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

  it('opens "New Test Run" drawer on button click', async () => {
    render(<TestRunsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-New Test Run'));
    expect(screen.getByTestId('test-run-drawer')).toBeInTheDocument();
  });

  it('calls onTotalCountChange with the total count', async () => {
    mockGetTestRuns.mockResolvedValue(
      makePaginatedResponse([makeTestRun('r-1'), makeTestRun('r-2')], 42)
    );
    const onTotalCountChange = jest.fn();
    render(
      <TestRunsTable
        sessionToken="tok"
        onTotalCountChange={onTotalCountChange}
      />
    );
    await waitFor(() => expect(onTotalCountChange).toHaveBeenCalledWith(42));
  });
});
