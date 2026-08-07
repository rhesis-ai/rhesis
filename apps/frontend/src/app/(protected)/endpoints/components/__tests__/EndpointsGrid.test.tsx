import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import EndpointsGrid from '../EndpointsGrid';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
  usePathname: () => '/endpoints',
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

const mockGetEndpoints = jest.fn();
const mockGetProjects = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getEndpointsClient: () => ({ getEndpoints: mockGetEndpoints }),
    getProjectsClient: () => ({ getProjects: mockGetProjects }),
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
    limit: 10,
    currentPage: 0,
    pageSize: 10,
    totalPages: 1,
  },
});

const makeEndpoint = (id: string, name = 'Endpoint') => ({
  id,
  name,
  status: { name: 'Active' },
});

describe('EndpointsGrid', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetProjects.mockResolvedValue([]);
    // Default: one row, so tests that don't care about emptiness exercise the
    // populated (grid) branch rather than the empty-state branch.
    mockGetEndpoints.mockResolvedValue(
      makePaginatedResponse([makeEndpoint('e-0')])
    );
  });

  it('renders the grid directly (no full-page loading/empty logic) when used without onCreateClick, e.g. embedded in a project tab', async () => {
    render(<EndpointsGrid projectId="p1" />);
    expect(await screen.findByTestId('base-data-grid')).toBeInTheDocument();
  });

  it('shows a loading state while the first fetch is in flight', () => {
    mockGetEndpoints.mockReturnValue(new Promise(() => {}));
    render(<EndpointsGrid canCreate onCreateClick={jest.fn()} />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.queryByTestId('base-data-grid')).not.toBeInTheDocument();
  });

  it('renders the empty state directly, without ever mounting the grid, when there are zero endpoints', async () => {
    mockGetEndpoints.mockResolvedValue(makePaginatedResponse([]));
    render(<EndpointsGrid canCreate onCreateClick={jest.fn()} />);
    expect(await screen.findByText('No endpoints yet')).toBeInTheDocument();
    expect(screen.queryByTestId('base-data-grid')).not.toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('renders the grid, not the empty state, when endpoints exist', async () => {
    render(<EndpointsGrid canCreate onCreateClick={jest.fn()} />);
    expect(await screen.findByTestId('row-e-0')).toBeInTheDocument();
    expect(screen.queryByText('No endpoints yet')).not.toBeInTheDocument();
  });

  it('shows the error alert instead of the empty state when the fetch fails', async () => {
    mockGetEndpoints.mockRejectedValue(new Error('Network error'));
    render(<EndpointsGrid canCreate onCreateClick={jest.fn()} />);
    expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    expect(screen.queryByText('No endpoints yet')).not.toBeInTheDocument();
  });
});
