import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestsPage from '../page';

const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn(), refresh: jest.fn() }),
  usePathname: () => '/tests',
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

jest.mock('@/contexts/OnboardingContext', () => ({
  useOnboarding: () => ({ activeTour: null, startTour: jest.fn() }),
}));

jest.mock('@/hooks/useEndpoints', () => ({
  useEndpoint: () => ({ data: undefined }),
}));

// TestsGrid owns the query and the loading/empty/populated decision itself —
// the page's only job is to wire `canCreate`/`onNewTest` through to it.
jest.mock('../components/TestsGrid', () => {
  return function MockTestsGrid({
    canCreate,
    onNewTest,
  }: {
    canCreate?: boolean;
    onNewTest?: () => void;
  }) {
    return (
      <button onClick={onNewTest} disabled={!canCreate}>
        mock-create-test
      </button>
    );
  };
});

jest.mock('@/app/(protected)/test-sets/components/FileImportDrawer', () => {
  return function MockFileImportDrawer() {
    return null;
  };
});

describe('TestsPage', () => {
  it('passes canCreate through to the grid', () => {
    render(<TestsPage />);
    expect(screen.getByText('mock-create-test')).toBeEnabled();
  });

  it('navigates to the manual test flow when the grid invokes onNewTest', async () => {
    render(<TestsPage />);
    await userEvent.click(screen.getByText('mock-create-test'));
    expect(mockPush).toHaveBeenCalledWith('/tests/new-manual');
  });
});
