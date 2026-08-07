import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import SourcesGrid from '../SourcesGrid';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
  usePathname: () => '/knowledge',
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

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

const mockGetSources = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getSourcesClient: () => ({ getSources: mockGetSources }),
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

const makeSource = (id: string, title = 'Source') => ({
  id,
  title,
});

describe('SourcesGrid', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Default: one row, so tests that don't care about emptiness exercise the
    // populated (grid) branch rather than the empty-state branch.
    mockGetSources.mockResolvedValue(
      makePaginatedResponse([makeSource('s-0')])
    );
  });

  it('shows a loading state while the first fetch is in flight', () => {
    mockGetSources.mockReturnValue(new Promise(() => {}));
    render(<SourcesGrid canCreate onCreateClick={jest.fn()} />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByTestId('base-data-grid')).not.toBeInTheDocument();
  });

  it('renders the empty state directly, without ever mounting the grid, when there are zero sources', async () => {
    mockGetSources.mockResolvedValue(makePaginatedResponse([]));
    render(<SourcesGrid canCreate onCreateClick={jest.fn()} />);
    expect(
      await screen.findByText('No knowledge sources yet')
    ).toBeInTheDocument();
    expect(screen.queryByTestId('base-data-grid')).not.toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('renders the grid, not the empty state, when sources exist', async () => {
    render(<SourcesGrid canCreate onCreateClick={jest.fn()} />);
    expect(await screen.findByTestId('row-s-0')).toBeInTheDocument();
    expect(
      screen.queryByText('No knowledge sources yet')
    ).not.toBeInTheDocument();
  });

  it('shows the error message instead of the empty state when the fetch fails', async () => {
    mockGetSources.mockRejectedValue(new Error('Network error'));
    render(<SourcesGrid canCreate onCreateClick={jest.fn()} />);
    expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    expect(
      screen.queryByText('No knowledge sources yet')
    ).not.toBeInTheDocument();
  });
});
