import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestSetsGrid from '../TestSetsGrid';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import type { UUID } from 'crypto';

// ---- Navigation + Auth ----

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: jest.fn() }),
  usePathname: () => '/test-sets',
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

const mockGetTestSets = jest.fn();
const mockDeleteTestSet = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestSetsClient: () => ({
      getTestSets: mockGetTestSets,
      deleteTestSet: mockDeleteTestSet,
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

jest.mock('../TestSetDrawer', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="test-set-drawer" /> : null,
}));

jest.mock('../TestRunDrawer', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="test-run-drawer" /> : null,
}));

jest.mock('../GarakImportDialog', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="garak-import-dialog" /> : null,
}));

jest.mock('../FileImportDialog', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="file-import-dialog" /> : null,
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

const makeTestSet = (id: UUID, name = 'Test Set'): TestSet => ({
  id,
  status: 'active',
  is_published: false,
  name,
  description: 'A test set',
  owner: { id: 'u1', name: 'Alice', email: 'alice@example.com' },
  tags: [],
  counts: { comments: 0, tasks: 0 },
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
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

// Helper: wait for the grid to finish loading (fetch triggered on mount)
async function waitForGrid() {
  await waitFor(() =>
    expect(screen.queryByTestId('grid-loading')).not.toBeInTheDocument()
  );
}

// ---- Tests ----

describe('TestSetsGrid', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Default: fetch returns empty so tests that don't care about rows stay fast
    mockGetTestSets.mockResolvedValue(makePaginatedResponse([]));
  });

  it('shows loading state while fetching', () => {
    mockGetTestSets.mockReturnValue(new Promise(() => {}));
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    expect(screen.getByTestId('grid-loading')).toBeInTheDocument();
  });

  it('renders rows returned by the fetch', async () => {
    mockGetTestSets.mockResolvedValue(
      makePaginatedResponse([
        makeTestSet('00000000-0000-0000-0000-000000000001' as UUID),
        makeTestSet('00000000-0000-0000-0000-000000000002' as UUID),
      ])
    );
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitFor(() =>
      expect(
        screen.getByTestId('row-00000000-0000-0000-0000-000000000001')
      ).toBeInTheDocument()
    );
    expect(
      screen.getByTestId('row-00000000-0000-0000-0000-000000000002')
    ).toBeInTheDocument();
  });

  it('renders "New Test Set" action button after loading', async () => {
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitForGrid();
    expect(screen.getByTestId('action-New Test Set')).toBeInTheDocument();
  });

  it('renders import action buttons after loading', async () => {
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitForGrid();
    expect(screen.getByTestId('action-Import from File')).toBeInTheDocument();
    expect(screen.getByTestId('action-Import from Garak')).toBeInTheDocument();
  });

  it('navigates to test-set detail on row click', async () => {
    mockGetTestSets.mockResolvedValue(
      makePaginatedResponse([
        makeTestSet('00000000-0000-0000-0000-000000000099' as UUID),
      ])
    );
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitFor(() =>
      expect(
        screen.getByTestId('row-00000000-0000-0000-0000-000000000099')
      ).toBeInTheDocument()
    );
    await userEvent.click(
      screen.getByTestId('row-00000000-0000-0000-0000-000000000099')
    );
    expect(mockPush).toHaveBeenCalledWith(
      '/test-sets/00000000-0000-0000-0000-000000000099'
    );
  });

  it('shows "Delete Test Sets" button when rows are selected', async () => {
    mockGetTestSets.mockResolvedValue(
      makePaginatedResponse([
        makeTestSet('00000000-0000-0000-0000-000000000001' as UUID),
      ])
    );
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitFor(() =>
      expect(
        screen.getByTestId('row-00000000-0000-0000-0000-000000000001')
      ).toBeInTheDocument()
    );

    await userEvent.click(
      screen.getByLabelText('select-00000000-0000-0000-0000-000000000001')
    );
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Test Sets')).toBeInTheDocument()
    );
  });

  it('hides delete button when no rows are selected', async () => {
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitForGrid();
    expect(
      screen.queryByTestId('action-Delete Test Sets')
    ).not.toBeInTheDocument();
  });

  it('opens delete modal when "Delete Test Sets" is clicked', async () => {
    mockGetTestSets.mockResolvedValue(
      makePaginatedResponse([
        makeTestSet('00000000-0000-0000-0000-000000000001' as UUID),
      ])
    );
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitFor(() =>
      expect(
        screen.getByTestId('row-00000000-0000-0000-0000-000000000001')
      ).toBeInTheDocument()
    );

    await userEvent.click(
      screen.getByLabelText('select-00000000-0000-0000-0000-000000000001')
    );
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Test Sets')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-Delete Test Sets'));
    expect(screen.getByTestId('delete-modal')).toBeInTheDocument();
  });

  it('calls deleteTestSet and shows success on confirm', async () => {
    mockDeleteTestSet.mockResolvedValue(undefined);
    mockGetTestSets.mockResolvedValue(
      makePaginatedResponse([
        makeTestSet('00000000-0000-0000-0000-000000000001' as UUID),
      ])
    );
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitFor(() =>
      expect(
        screen.getByTestId('row-00000000-0000-0000-0000-000000000001')
      ).toBeInTheDocument()
    );

    await userEvent.click(
      screen.getByLabelText('select-00000000-0000-0000-0000-000000000001')
    );
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Test Sets')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-Delete Test Sets'));
    await userEvent.click(
      screen.getByRole('button', { name: /confirm delete/i })
    );

    await waitFor(() =>
      expect(mockDeleteTestSet).toHaveBeenCalledWith(
        '00000000-0000-0000-0000-000000000001'
      )
    );
    await waitFor(() =>
      expect(mockShow).toHaveBeenCalledWith(
        expect.stringContaining('deleted'),
        expect.objectContaining({ severity: 'success' })
      )
    );
  });

  it('cancels deletion without calling API', async () => {
    mockGetTestSets.mockResolvedValue(
      makePaginatedResponse([
        makeTestSet('00000000-0000-0000-0000-000000000001' as UUID),
      ])
    );
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitFor(() =>
      expect(
        screen.getByTestId('row-00000000-0000-0000-0000-000000000001')
      ).toBeInTheDocument()
    );

    await userEvent.click(
      screen.getByLabelText('select-00000000-0000-0000-0000-000000000001')
    );
    await waitFor(() =>
      expect(screen.getByTestId('action-Delete Test Sets')).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId('action-Delete Test Sets'));
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(mockDeleteTestSet).not.toHaveBeenCalled();
  });

  it('opens TestSetDrawer when "New Test Set" is clicked', async () => {
    render(<TestSetsGrid testSets={[]} loading={false} sessionToken="tok" />);
    await waitForGrid();
    await userEvent.click(screen.getByTestId('action-New Test Set'));
    expect(screen.getByTestId('test-set-drawer')).toBeInTheDocument();
  });
});
