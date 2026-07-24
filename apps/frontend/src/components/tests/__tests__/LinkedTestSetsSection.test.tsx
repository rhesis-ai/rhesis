import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LinkedTestSetsSection from '../LinkedTestSetsSection';

let mockCanEdit = true;

jest.mock('@/components/common/Can', () => ({
  useCan: () => mockCanEdit,
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

jest.mock('@/utils/api-client/test-sets-client', () => ({
  TestSetsClient: jest.fn().mockImplementation(() => ({
    getTestSets: jest.fn().mockResolvedValue({ data: [] }),
    associateTestsWithTestSet: jest.fn(),
  })),
}));

// Always render a marker (regardless of `open`) so tests can distinguish
// "component gated out of the tree entirely" from "mounted but closed".
jest.mock('@/components/common/AssignEntityDrawer', () => ({
  __esModule: true,
  default: ({ open }: { open: boolean }) => (
    <div data-testid="assign-drawer" data-open={String(open)} />
  ),
}));

describe('LinkedTestSetsSection', () => {
  beforeEach(() => {
    mockCanEdit = true;
    mockGetLinkedTestSets.mockReset();
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
});
