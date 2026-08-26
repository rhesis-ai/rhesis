import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import EntityGrid from '../EntityGrid';
import { defineList } from '@/utils/list';
import type { BulkDeleteActionsState } from '@/hooks/useBulkDelete';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockRouterPush, refresh: jest.fn() }),
  usePathname: () => '/widgets',
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn(), close: jest.fn() }),
  NotificationProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({})),
}));

// Toolbar buttons that require a live DataGrid api context.
jest.mock('@mui/x-data-grid', () => {
  const actual = jest.requireActual('@mui/x-data-grid');
  return {
    ...actual,
    GridToolbarColumnsButton: () => null,
    GridToolbarDensitySelector: () => null,
    GridToolbarExport: () => <button data-testid="export-button" />,
  };
});

const mockRouterPush = jest.fn();

interface MockGridProps {
  rows: Array<Record<string, unknown>>;
  loading?: boolean;
  columns?: Array<{
    field: string;
    renderCell?: (params: {
      id: unknown;
      row: Record<string, unknown>;
    }) => React.ReactNode;
  }>;
  toolbarSlot?: React.ComponentType;
  onRowClick?: (p: { id: unknown; row: Record<string, unknown> }) => void;
  onRowSelectionModelChange?: (model: string[]) => void;
  checkboxSelection?: boolean;
}

jest.mock('@/components/common/BaseDataGrid', () => {
  const MockBaseDataGrid = ({
    rows,
    loading,
    columns,
    toolbarSlot: ToolbarSlot,
    onRowClick,
    onRowSelectionModelChange,
    checkboxSelection,
  }: MockGridProps) => {
    // Like the real DataGrid: loading shows an overlay, the toolbar stays mounted.
    const actionsCol = columns?.find(c => c.field === 'actions');
    return (
      <div data-testid="base-data-grid">
        {loading && <div data-testid="grid-loading" />}
        {ToolbarSlot && <ToolbarSlot />}
        {checkboxSelection && (
          <button
            data-testid="select-all"
            onClick={() =>
              onRowSelectionModelChange?.(rows.map(r => String(r.id)))
            }
          />
        )}
        {rows.map(row => (
          <div
            key={String(row.id)}
            role="row"
            data-testid={`row-${row.id}`}
            onClick={() => onRowClick?.({ id: row.id, row })}
          >
            <span>{String(row.name)}</span>
            {actionsCol?.renderCell?.({ id: row.id, row })}
          </div>
        ))}
      </div>
    );
  };
  MockBaseDataGrid.GRID_PAPER_SX = {};
  return {
    __esModule: true,
    default: MockBaseDataGrid,
    GRID_PAPER_SX: {},
  };
});

const mockList = jest.fn();
const mockBulkDelete = jest.fn();
const mockDeleteOne = jest.fn();

const makeResponse = (
  data: Array<Record<string, unknown>>,
  total?: number
) => ({
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

const makeWidget = (id: string, name = `Widget ${id}`) => ({ id, name });

const widgetsList = defineList({
  title: 'Widgets',
  resource: 'widgets',
  capability: 'widget:read',
  defaultPageSize: 25,
  filters: {
    search: { kind: 'search', columns: ['name'] },
    status: { kind: 'enum', column: 'status' },
  },
  list: (_factory, params) => mockList(params),
  delete: {
    bulk: (_factory, ids) => mockBulkDelete(ids),
    capability: 'widget:delete',
    capabilityMode: 'ambient',
    labelSingular: 'widget',
    labelPlural: 'widgets',
  },
});

const readOnlyList = defineList({
  title: 'Widgets',
  resource: 'widgets',
  capability: 'widget:read',
  defaultPageSize: 25,
  filters: { search: { kind: 'search', columns: ['name'] } },
  list: (_factory, params) => mockList(params),
});

const singleDeleteList = defineList({
  title: 'Widgets',
  resource: 'widgets',
  capability: 'widget:read',
  defaultPageSize: 25,
  filters: { search: { kind: 'search', columns: ['name'] } },
  list: (_factory, params) => mockList(params),
  delete: {
    one: (_factory, id) => mockDeleteOne(id),
    capability: 'widget:delete',
    capabilityMode: 'ambient',
    labelSingular: 'widget',
    labelPlural: 'widgets',
  },
});

const columns = [{ field: 'name', headerName: 'Name', flex: 1 }];

const baseProps = {
  columns,
  toFilters: (state: { search: string; pill: string }) => ({
    search: state.search,
    status: state.pill,
  }),
  emptyState: <div data-testid="empty-state">No widgets yet</div>,
};

describe('EntityGrid', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockList.mockResolvedValue(makeResponse([makeWidget('w-1')]));
  });

  it('shows a loading state while the first fetch is in flight', () => {
    mockList.mockReturnValue(new Promise(() => {}));
    render(<EntityGrid descriptor={widgetsList} {...baseProps} />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByTestId('base-data-grid')).not.toBeInTheDocument();
  });

  it('renders the empty state, never the grid, when there are zero rows', async () => {
    mockList.mockResolvedValue(makeResponse([]));
    render(<EntityGrid descriptor={widgetsList} {...baseProps} />);
    expect(await screen.findByTestId('empty-state')).toBeInTheDocument();
    expect(screen.queryByTestId('base-data-grid')).not.toBeInTheDocument();
  });

  it('renders rows when data exists', async () => {
    render(<EntityGrid descriptor={widgetsList} {...baseProps} />);
    expect(await screen.findByTestId('row-w-1')).toBeInTheDocument();
    expect(screen.queryByTestId('empty-state')).not.toBeInTheDocument();
  });

  it('bypasses the gate when embedded', async () => {
    mockList.mockResolvedValue(makeResponse([]));
    render(<EntityGrid descriptor={widgetsList} {...baseProps} embedded />);
    expect(await screen.findByTestId('base-data-grid')).toBeInTheDocument();
    expect(screen.queryByTestId('empty-state')).not.toBeInTheDocument();
  });

  it('shows a dismissible error alert when the fetch fails', async () => {
    mockList.mockRejectedValue(new Error('Network error'));
    render(<EntityGrid descriptor={widgetsList} {...baseProps} />);
    const alert = await screen.findByText(/network error/i);
    expect(alert).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /close/i }));
    await waitFor(() =>
      expect(screen.queryByText(/network error/i)).not.toBeInTheDocument()
    );
  });

  it('sends the search box value into the descriptor filter', async () => {
    render(<EntityGrid descriptor={widgetsList} {...baseProps} />);
    await screen.findByTestId('row-w-1');

    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText('Search widgets…'), 'abc');

    await waitFor(() => {
      const lastCall = mockList.mock.calls.at(-1)?.[0];
      expect(String(lastCall?.$filter ?? '')).toContain('abc');
    });
  });

  it('maps an active pill into the descriptor filter and back to none on the all pill', async () => {
    render(
      <EntityGrid
        descriptor={widgetsList}
        {...baseProps}
        pills={{
          tabs: [
            { label: 'All', value: 'all' },
            { label: 'Active', value: 'active' },
          ],
        }}
      />
    );
    await screen.findByTestId('row-w-1');

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Active' }));
    await waitFor(() => {
      const lastCall = mockList.mock.calls.at(-1)?.[0];
      expect(String(lastCall?.$filter ?? '')).toContain('active');
    });

    await user.click(screen.getByRole('button', { name: 'All' }));
    await waitFor(() => {
      const lastCall = mockList.mock.calls.at(-1)?.[0];
      expect(String(lastCall?.$filter ?? '')).not.toContain('active');
    });
  });

  it('renders a delete action that opens the confirm modal and calls the bulk endpoint', async () => {
    mockBulkDelete.mockResolvedValue(undefined);
    render(<EntityGrid descriptor={widgetsList} {...baseProps} />);
    await screen.findByTestId('row-w-1');

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /delete/i }));
    expect(await screen.findByText('Delete Widget')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^delete$/i }));
    await waitFor(() => expect(mockBulkDelete).toHaveBeenCalledWith(['w-1']));
  });

  it('uses the single-delete endpoint when the descriptor has no bulk delete', async () => {
    mockDeleteOne.mockResolvedValue(undefined);
    render(<EntityGrid descriptor={singleDeleteList} {...baseProps} />);
    await screen.findByTestId('row-w-1');

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /delete/i }));
    await user.click(await screen.findByRole('button', { name: /^delete$/i }));
    await waitFor(() => expect(mockDeleteOne).toHaveBeenCalledWith('w-1'));
    expect(mockBulkDelete).not.toHaveBeenCalled();

    // No bulk endpoint ⇒ no selection toggle either.
    expect(screen.queryByText('Select widgets')).not.toBeInTheDocument();
  });

  it('renders no actions column and no selection toggle for a read-only descriptor', async () => {
    render(<EntityGrid descriptor={readOnlyList} {...baseProps} />);
    await screen.findByTestId('row-w-1');
    expect(
      screen.queryByRole('button', { name: /delete/i })
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Select widgets')).not.toBeInTheDocument();
  });

  it('pushes extended bulk actions through buildBulkActions when the selection changes', async () => {
    const onBulkActionsChange = jest.fn();
    render(
      <EntityGrid
        descriptor={widgetsList}
        {...baseProps}
        onBulkActionsChange={onBulkActionsChange}
        buildBulkActions={(base: BulkDeleteActionsState, ctx) => ({
          ...base,
          selectedCount: ctx.selectedIds.length,
        })}
      />
    );
    await screen.findByTestId('row-w-1');

    const user = userEvent.setup();
    await user.click(screen.getByLabelText(/select widgets/i));
    await user.click(await screen.findByTestId('select-all'));

    await waitFor(() =>
      expect(onBulkActionsChange).toHaveBeenLastCalledWith(
        expect.objectContaining({ visible: true, selectedCount: 1 })
      )
    );
  });

  it('navigates to getRowUrl on row click', async () => {
    render(
      <EntityGrid
        descriptor={widgetsList}
        {...baseProps}
        getRowUrl={row => `/widgets/${(row as { id: string }).id}`}
      />
    );
    const user = userEvent.setup();
    await user.click(await screen.findByTestId('row-w-1'));
    expect(mockRouterPush).toHaveBeenCalledWith('/widgets/w-1');
  });

  it('refetches when refreshTrigger is bumped', async () => {
    const { rerender } = render(
      <EntityGrid descriptor={widgetsList} {...baseProps} refreshTrigger={0} />
    );
    await screen.findByTestId('row-w-1');
    const callsBefore = mockList.mock.calls.length;

    rerender(
      <EntityGrid descriptor={widgetsList} {...baseProps} refreshTrigger={1} />
    );
    await waitFor(() =>
      expect(mockList.mock.calls.length).toBeGreaterThan(callsBefore)
    );
  });
});
