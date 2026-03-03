import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestsTable from '../TestsGrid';

// ---- Navigation + Auth ----

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: jest.fn() }),
  usePathname: () => '/tests',
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

const mockGetTests = jest.fn();
const mockDeleteTest = jest.fn();
const mockGetTestSetsForSelect = jest.fn();
const mockAssociateTestsWithTestSet = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestsClient: () => ({
      getTests: mockGetTests,
      deleteTest: mockDeleteTest,
    }),
  })),
}));

jest.mock('@/utils/api-client/test-sets-client', () => ({
  TestSetsClient: jest.fn().mockImplementation(() => ({
    getTestSets: mockGetTestSetsForSelect,
    associateTestsWithTestSet: mockAssociateTestsWithTestSet,
  })),
}));

// ---- BaseDataGrid stub ----
// Renders action buttons and rows so we can test container behaviour without
// the full MUI DataGrid virtualized canvas.

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

jest.mock('../TestDrawer', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="test-drawer" /> : null,
}));

jest.mock('../TestSetSelectionDialog', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="test-set-dialog" /> : null,
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

const makeTest = (id: string, content = 'Test content') => ({
  id,
  prompt: { content },
  behavior: { name: 'Safety' },
  topic: { name: 'Topic A' },
  category: { name: 'Cat 1' },
  test_type: { type_value: 'adversarial' },
  tags: [],
  counts: { comments: 0, tasks: 0 },
  created_at: '2024-01-01T00:00:00Z',
});

const makePaginatedResponse = <T,>(data: T[], total?: number) => ({
  data,
  pagination: {
    totalCount: total ?? data.length,
    skip: 0,
    limit: 25,
    currentPage: 0,
    pageSize: 25,
    totalPages: 1,
  },
});

// ---- Tests ----

describe('TestsTable', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetTests.mockResolvedValue(makePaginatedResponse([]));
  });

  it('shows loading state while fetching', () => {
    mockGetTests.mockReturnValue(new Promise(() => {}));
    render(<TestsTable sessionToken="tok" />);
    expect(screen.getByTestId('grid-loading')).toBeInTheDocument();
  });

  it('renders "Add Tests" action button', async () => {
    render(<TestsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
    );
    expect(screen.getByTestId('action-Add Tests')).toBeInTheDocument();
  });

  it('renders rows after data loads', async () => {
    mockGetTests.mockResolvedValue(
      makePaginatedResponse([makeTest('t-1'), makeTest('t-2')])
    );
    render(<TestsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );
    expect(screen.getByTestId('row-t-2')).toBeInTheDocument();
  });

  it('shows error alert when fetch fails', async () => {
    mockGetTests.mockRejectedValue(new Error('Network error'));
    render(<TestsTable sessionToken="tok" />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText(/failed to load tests/i)).toBeInTheDocument();
  });

  it('navigates to test detail on row click', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-42')]));
    render(<TestsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-42')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('row-t-42'));
    expect(mockPush).toHaveBeenCalledWith('/tests/t-42');
  });

  it('shows "Delete Tests" button when rows are selected', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    render(<TestsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Tests')).toBeInTheDocument()
    );
  });

  it('shows "Assign to Test Set" button when rows are selected', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    render(<TestsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(
        screen.getByTestId('action-Assign to Test Set')
      ).toBeInTheDocument()
    );
  });

  it('opens delete modal and confirms deletion', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    mockDeleteTest.mockResolvedValue(undefined);
    render(<TestsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Tests')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-Delete Tests'));
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );
    await waitFor(() => expect(mockDeleteTest).toHaveBeenCalledWith('t-1'));
    await waitFor(() =>
      expect(mockShow).toHaveBeenCalledWith(
        expect.stringContaining('deleted'),
        expect.objectContaining({ severity: 'success' })
      )
    );
  });

  it('cancels deletion without calling API', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    render(<TestsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Tests')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-Delete Tests'));

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(mockDeleteTest).not.toHaveBeenCalled();
  });

  it('shows error notification when delete fails', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    mockDeleteTest.mockRejectedValue(new Error('Server error'));
    render(<TestsTable sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Tests')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-Delete Tests'));
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

  it('disables "Add Tests" button when disableAddButton=true', async () => {
    render(<TestsTable sessionToken="tok" disableAddButton />);
    await waitFor(() =>
      expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
    );
    expect(screen.getByTestId('action-Add Tests')).toBeDisabled();
  });
});
