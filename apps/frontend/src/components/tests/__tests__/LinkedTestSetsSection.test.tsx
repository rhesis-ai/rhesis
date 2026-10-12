import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LinkedTestSetsSection from '../LinkedTestSetsSection';

let mockCanEdit = true;

jest.mock('@/components/common/Can', () => ({
  useCan: () => mockCanEdit,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => mockCanEdit,
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({ status: 'authenticated' }),
}));

const mockShowNotification = jest.fn();

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: mockShowNotification }),
}));

const mockGetLinkedTestSets = jest.fn();

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getTestsClient: () => ({
      getLinkedTestSets: mockGetLinkedTestSets,
    }),
  })),
}));

const mockGetTestSets = jest.fn();

jest.mock('@/utils/api-client/test-sets-client', () => ({
  TestSetsClient: jest.fn().mockImplementation(() => ({
    getTestSets: mockGetTestSets,
    associateTestsWithTestSet: jest.fn(),
  })),
}));

let mockDrawerProps: Record<string, unknown> = {};

// Always render a marker (regardless of `open`) so tests can distinguish
// "component gated out of the tree entirely" from "mounted but closed".
jest.mock('@/components/common/AssignEntityDrawer', () => ({
  __esModule: true,
  default: (props: { open: boolean }) => {
    mockDrawerProps = props;
    return <div data-testid="assign-drawer" data-open={String(props.open)} />;
  },
}));

describe('LinkedTestSetsSection', () => {
  beforeEach(() => {
    mockCanEdit = true;
    mockGetLinkedTestSets.mockReset();
    mockGetTestSets.mockReset();
    mockShowNotification.mockReset();
    mockGetTestSets.mockResolvedValue({
      data: [],
      pagination: { totalCount: 0 },
    });
  });

  it('hides Assign controls for Viewer (empty state)', async () => {
    mockCanEdit = false;
    mockGetLinkedTestSets.mockResolvedValue({
      data: [],
      pagination: { totalCount: 0 },
    });

    render(<LinkedTestSetsSection testId="test-1" />);

    await waitFor(() =>
      expect(screen.getByText('No test sets assigned yet')).toBeInTheDocument()
    );

    expect(
      screen.queryByRole('button', { name: /assign to test set/i })
    ).not.toBeInTheDocument();
    expect(
      screen.getByText('This test has no linked test sets yet.')
    ).toBeInTheDocument();
    // Drawer is gated out of the tree entirely for viewers, not just closed.
    expect(screen.queryByTestId('assign-drawer')).not.toBeInTheDocument();
  });

  it('hides Assign button for Viewer when test sets are linked', async () => {
    mockCanEdit = false;
    mockGetLinkedTestSets.mockResolvedValue({
      data: [
        {
          id: 'ts-1',
          name: 'Test Set 1',
          description: 'desc',
          created_at: '2024-01-01T00:00:00Z',
        },
      ],
      pagination: { totalCount: 1 },
    });

    render(<LinkedTestSetsSection testId="test-1" />);

    await waitFor(() =>
      expect(screen.getByText('Linked Test Sets (1)')).toBeInTheDocument()
    );

    expect(
      screen.queryByRole('button', { name: /^assign$/i })
    ).not.toBeInTheDocument();
  });

  it('shows Assign controls for Member/Admin/Owner and opens the drawer on click', async () => {
    mockCanEdit = true;
    mockGetLinkedTestSets.mockResolvedValue({
      data: [],
      pagination: { totalCount: 0 },
    });

    render(<LinkedTestSetsSection testId="test-1" />);

    const assignButton = await screen.findByRole('button', {
      name: /assign to test set/i,
    });

    // Drawer is mounted (gating allows it) but closed until clicked.
    expect(screen.getByTestId('assign-drawer')).toHaveAttribute(
      'data-open',
      'false'
    );

    await userEvent.click(assignButton);

    await waitFor(() =>
      expect(screen.getByTestId('assign-drawer')).toHaveAttribute(
        'data-open',
        'true'
      )
    );
  });

  it('pages and searches test sets server-side, excluding linked ones', async () => {
    mockGetLinkedTestSets.mockResolvedValue({
      data: [],
      pagination: { totalCount: 0 },
    });

    render(<LinkedTestSetsSection testId="test-1" />);
    await userEvent.click(
      await screen.findByRole('button', { name: /assign to test set/i })
    );

    await waitFor(() => expect(mockGetTestSets).toHaveBeenCalled());
    expect(mockGetTestSets).toHaveBeenLastCalledWith(
      expect.objectContaining({
        skip: 0,
        limit: 25,
        $filter: "not tests/any(t: t/id eq 'test-1')",
      })
    );

    act(() => {
      (mockDrawerProps.onSearchQueryChange as (q: string) => void)("O'Brien");
    });

    await waitFor(() =>
      expect(mockGetTestSets).toHaveBeenLastCalledWith(
        expect.objectContaining({
          skip: 0,
          $filter:
            "not tests/any(t: t/id eq 'test-1') and " +
            "(contains(tolower(name), tolower('O''Brien')) or " +
            "contains(tolower(description), tolower('O''Brien')))",
        })
      )
    );

    act(() => {
      (
        mockDrawerProps.onPaginationModelChange as (m: {
          page: number;
          pageSize: number;
        }) => void
      )({ page: 2, pageSize: 10 });
    });

    await waitFor(() =>
      expect(mockGetTestSets).toHaveBeenLastCalledWith(
        expect.objectContaining({ skip: 20, limit: 10 })
      )
    );
  });

  it('ignores a test set request that fails after the drawer closes', async () => {
    mockGetLinkedTestSets.mockResolvedValue({
      data: [],
      pagination: { totalCount: 0 },
    });
    let rejectRequest: (error: Error) => void = () => {};
    mockGetTestSets.mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectRequest = reject;
      })
    );

    render(<LinkedTestSetsSection testId="test-1" />);
    await userEvent.click(
      await screen.findByRole('button', { name: /assign to test set/i })
    );
    await waitFor(() => expect(mockGetTestSets).toHaveBeenCalled());

    act(() => {
      (mockDrawerProps.onClose as () => void)();
    });
    await waitFor(() =>
      expect(screen.getByTestId('assign-drawer')).toHaveAttribute(
        'data-open',
        'false'
      )
    );

    await act(async () => {
      rejectRequest(new Error('network'));
    });

    expect(mockShowNotification).not.toHaveBeenCalled();
  });
});
