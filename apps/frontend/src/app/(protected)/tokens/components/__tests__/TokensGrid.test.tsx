import React from 'react';
import { render, screen, waitFor } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TokensGrid from '../TokensGrid';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
  usePathname: () => '/tokens',
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

const mockListTokens = jest.fn();
const mockBulkDeleteTokens = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTokensClient: () => ({
      listTokens: mockListTokens,
      bulkDeleteTokens: mockBulkDeleteTokens,
    }),
  })),
}));

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
}

jest.mock('@/components/common/BaseDataGrid', () => {
  const MockBaseDataGrid = ({ rows, loading, columns }: MockGridProps) => {
    if (loading) return <div data-testid="grid-loading">Loading…</div>;
    const actionsCol = columns?.find(c => c.field === 'actions');
    return (
      <div data-testid="base-data-grid">
        {rows.map(row => (
          <div key={String(row.id)} data-testid={`row-${row.id}`}>
            <span>{String(row.name)}</span>
            {actionsCol?.renderCell?.({ id: row.id, row })}
          </div>
        ))}
      </div>
    );
  };
  return {
    __esModule: true,
    default: MockBaseDataGrid,
    GRID_PAPER_SX: {},
  };
});

jest.mock('../RefreshTokenModal', () => ({
  __esModule: true,
  default: ({
    open,
    onClose,
    onRefresh,
    tokenName,
  }: {
    open: boolean;
    onClose: () => void;
    onRefresh: (days: number | null) => Promise<void>;
    tokenName: string;
  }) =>
    open ? (
      <div data-testid="refresh-modal">
        <span data-testid="refresh-token-name">{tokenName}</span>
        <button onClick={() => onRefresh(30)}>confirm-refresh</button>
        <button onClick={onClose}>close-refresh</button>
      </div>
    ) : null,
}));

const onRefreshToken = jest.fn().mockResolvedValue(undefined);

const makeResponse = (data: Array<Record<string, unknown>>) => ({
  data,
  pagination: {
    totalCount: data.length,
    skip: 0,
    limit: 10,
    currentPage: 0,
    pageSize: 10,
    totalPages: 1,
  },
});

function makeToken(id: string) {
  return {
    id,
    name: `Token ${id}`,
    token_obfuscated: `rhesis_****${id}`,
    token_type: 'Bearer',
    user_id: 'u1',
    last_used_at: undefined,
    expires_at: '',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

describe('TokensGrid', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockListTokens.mockResolvedValue(makeResponse([makeToken('t1')]));
  });

  it('shows the empty state when there are no tokens', async () => {
    mockListTokens.mockResolvedValue(makeResponse([]));
    render(<TokensGrid onRefreshToken={onRefreshToken} />);
    expect(await screen.findByText('No API tokens yet')).toBeInTheDocument();
    expect(screen.queryByTestId('base-data-grid')).not.toBeInTheDocument();
  });

  it('renders token rows fetched through the descriptor', async () => {
    mockListTokens.mockResolvedValue(
      makeResponse([makeToken('t1'), makeToken('t2')])
    );
    render(<TokensGrid onRefreshToken={onRefreshToken} />);
    expect(await screen.findByText('Token t1')).toBeInTheDocument();
    expect(screen.getByText('Token t2')).toBeInTheDocument();
  });

  it('opens the refresh modal from the row action and calls onRefreshToken', async () => {
    render(<TokensGrid onRefreshToken={onRefreshToken} />);
    await screen.findByText('Token t1');

    const user = userEvent.setup();
    await user.click(
      screen.getByRole('button', { name: /invalidate and refresh/i })
    );
    expect(screen.getByTestId('refresh-modal')).toBeInTheDocument();
    expect(screen.getByTestId('refresh-token-name')).toHaveTextContent(
      'Token t1'
    );

    await user.click(screen.getByRole('button', { name: 'confirm-refresh' }));
    await waitFor(() => expect(onRefreshToken).toHaveBeenCalledWith('t1', 30));
  });

  it('deletes a token through the row delete action', async () => {
    mockBulkDeleteTokens.mockResolvedValue({ deleted_ids: ['t1'] });
    render(<TokensGrid onRefreshToken={onRefreshToken} />);
    await screen.findByText('Token t1');

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /delete/i }));
    await user.click(await screen.findByRole('button', { name: /^delete$/i }));
    await waitFor(() =>
      expect(mockBulkDeleteTokens).toHaveBeenCalledWith(['t1'])
    );
  });
});
