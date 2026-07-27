import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestSetsPage from '../page';

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    refresh: jest.fn(),
  }),
  usePathname: () => '/test-sets',
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { session_token: 'tok', user: { id: 'u1', name: 'Alice' } },
    status: 'authenticated',
  }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => true,
  useCanWithStatus: () => ({ allowed: true, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => true,
}));

jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn(), close: jest.fn() }),
  NotificationProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

// TestSetsGrid owns the query and the loading/empty/populated decision
// itself (see TestSetsGrid.test.tsx for that behavior) — the page's only
// job is to wire `canCreate` and `onCreateClick` through to it correctly.
jest.mock('../components/TestSetsGrid', () => {
  return function MockTestSetsGrid({
    canCreate,
    onCreateClick,
  }: {
    canCreate?: boolean;
    onCreateClick?: () => void;
  }) {
    return (
      <button onClick={onCreateClick} disabled={!canCreate}>
        mock-create-test-set
      </button>
    );
  };
});

jest.mock('../components/TestSetDrawer', () => {
  return function MockTestSetDrawer({ open }: { open: boolean }) {
    return open ? <div data-testid="test-set-drawer" /> : null;
  };
});

jest.mock('../components/FileImportDrawer', () => {
  return function MockFileImportDrawer() {
    return null;
  };
});

jest.mock('../components/GarakImportDrawer', () => {
  return function MockGarakImportDrawer() {
    return null;
  };
});

describe('TestSetsPage', () => {
  it('passes canCreate through to the grid', () => {
    render(<TestSetsPage />);
    expect(screen.getByText('mock-create-test-set')).toBeEnabled();
  });

  it('opens the create drawer when the grid invokes onCreateClick', async () => {
    render(<TestSetsPage />);
    await userEvent.click(screen.getByText('mock-create-test-set'));
    expect(screen.getByTestId('test-set-drawer')).toBeInTheDocument();
  });
});
