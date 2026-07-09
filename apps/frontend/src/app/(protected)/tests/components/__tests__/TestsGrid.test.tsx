import React from 'react';
import { render, screen, waitFor, within } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestsTable, { TestsBulkActionsState } from '../TestsGrid';

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

jest.mock('@mui/x-data-grid', () => {
  const actual = jest.requireActual('@mui/x-data-grid');
  return {
    ...actual,
    GridToolbarColumnsButton: () => null,
    GridToolbarDensitySelector: () => null,
    GridToolbarExport: () => null,
  };
});

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
    toolbarSlot: ToolbarSlot,
  }: {
    rows: Array<Record<string, unknown>>;
    loading?: boolean;
    actionButtons?: ActionButton[];
    onRowClick?: (p: { id: unknown; row: Record<string, unknown> }) => void;
    checkboxSelection?: boolean;
    onRowSelectionModelChange?: (sel: unknown[]) => void;
    rowSelectionModel?: unknown[];
    toolbarSlot?: React.ComponentType;
  }) {
    if (loading) return <div data-testid="grid-loading">Loading…</div>;
    const enableSelection =
      checkboxSelection ?? Boolean(onRowSelectionModelChange);
    return (
      <div data-testid="base-data-grid">
        {ToolbarSlot ? <ToolbarSlot /> : null}
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
            {enableSelection && (
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

jest.mock('../TestSetSelectionDrawer', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="test-set-drawer" /> : null,
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

// ---- Helpers ----

async function enableSelectionMode() {
  await userEvent.click(screen.getByRole('switch', { name: /select tests/i }));
}

function TestsTableHarness(props: React.ComponentProps<typeof TestsTable>) {
  const bulkRef = React.useRef<TestsBulkActionsState>({
    visible: false,
    assignDisabled: false,
    onAssign: () => {},
    onDelete: () => {},
  });
  const [, setTick] = React.useState(0);

  // Stable identity: TestsGrid's onBulkActionsChange effect depends on this
  // callback by reference. An inline arrow here would get a new identity on
  // every render, and since it unconditionally calls setTick, that becomes an
  // infinite effect -> setTick -> re-render -> new reference -> effect loop.
  const handleBulkActionsChange = React.useCallback(
    (actions: TestsBulkActionsState) => {
      bulkRef.current = actions;
      setTick(t => t + 1);
    },
    []
  );

  return (
    <>
      {bulkRef.current.visible && (
        <>
          <button
            type="button"
            data-testid="bulk-assign"
            aria-label="Assign to Test Set"
            disabled={bulkRef.current.assignDisabled}
            onClick={() => bulkRef.current.onAssign()}
          >
            Assign to Test Set
          </button>
          <button
            type="button"
            data-testid="bulk-delete"
            aria-label="Delete Tests"
            onClick={() => bulkRef.current.onDelete()}
          >
            Delete Tests
          </button>
        </>
      )}
      <TestsTable {...props} onBulkActionsChange={handleBulkActionsChange} />
    </>
  );
}

// ---- Tests ----

describe('TestsTable', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetTests.mockResolvedValue(makePaginatedResponse([]));
  });

  it('shows loading state while fetching', () => {
    mockGetTests.mockReturnValue(new Promise(() => {}));
    render(<TestsTableHarness sessionToken="tok" />);
    expect(screen.getByTestId('grid-loading')).toBeInTheDocument();
  });

  it('renders no action buttons when no rows are selected', async () => {
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
    );
    expect(screen.queryByTestId('action-Add Tests')).not.toBeInTheDocument();
  });

  it('renders rows after data loads', async () => {
    mockGetTests.mockResolvedValue(
      makePaginatedResponse([makeTest('t-1'), makeTest('t-2')])
    );
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );
    expect(screen.getByTestId('row-t-2')).toBeInTheDocument();
  });

  it('shows error alert when fetch fails', async () => {
    mockGetTests.mockRejectedValue(new Error('Network error'));
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it('dismisses the error alert on close', async () => {
    mockGetTests.mockRejectedValue(new Error('Network error'));
    render(<TestsTableHarness sessionToken="tok" />);
    const alert = await screen.findByRole('alert');
    await userEvent.click(within(alert).getByLabelText(/close/i));
    await waitFor(() =>
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    );
  });

  it('navigates to test detail on row click', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-42')]));
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-42')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('row-t-42'));
    expect(mockPush).toHaveBeenCalledWith('/tests/t-42');
  });

  it('does not show row checkboxes until selection mode is enabled', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );
    expect(screen.queryByLabelText('select-t-1')).not.toBeInTheDocument();
  });

  it('shows "Delete Tests" FAB when rows are selected in selection mode', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await enableSelectionMode();
    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /delete tests/i })
      ).toBeInTheDocument()
    );
  });

  it('shows "Assign to Test Set" FAB when rows are selected in selection mode', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await enableSelectionMode();
    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /assign to test set/i })
      ).toBeInTheDocument()
    );
  });

  it('opens delete modal and confirms deletion', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    mockDeleteTest.mockResolvedValue(undefined);
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await enableSelectionMode();
    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /delete tests/i })
      ).toBeInTheDocument()
    );
    await userEvent.click(
      screen.getByRole('button', { name: /delete tests/i })
    );
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
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await enableSelectionMode();
    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /delete tests/i })
      ).toBeInTheDocument()
    );
    await userEvent.click(
      screen.getByRole('button', { name: /delete tests/i })
    );

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(mockDeleteTest).not.toHaveBeenCalled();
  });

  it('shows error notification when delete fails', async () => {
    mockGetTests.mockResolvedValue(makePaginatedResponse([makeTest('t-1')]));
    mockDeleteTest.mockRejectedValue(new Error('Server error'));
    render(<TestsTableHarness sessionToken="tok" />);
    await waitFor(() =>
      expect(screen.getByTestId('row-t-1')).toBeInTheDocument()
    );

    await enableSelectionMode();
    await userEvent.click(screen.getByLabelText('select-t-1'));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /delete tests/i })
      ).toBeInTheDocument()
    );
    await userEvent.click(
      screen.getByRole('button', { name: /delete tests/i })
    );
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

  it('renders no action buttons when disableAddButton=true and nothing selected', async () => {
    render(<TestsTable sessionToken="tok" disableAddButton />);
    await waitFor(() =>
      expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
    );
    expect(screen.queryByTestId('action-Add Tests')).not.toBeInTheDocument();
  });
});
