import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TestRunsPage from '../page';

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    refresh: jest.fn(),
  }),
  usePathname: () => '/test-runs',
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

// TestRunsGrid owns the query and the loading/empty/populated decision
// itself — the page's only job is to wire `canCreate`/`onCreateClick`
// through to it correctly.
jest.mock('../components/TestRunsGrid', () => {
  return function MockTestRunsGrid({
    canCreate,
    onCreateClick,
  }: {
    canCreate?: boolean;
    onCreateClick?: () => void;
  }) {
    return (
      <button onClick={onCreateClick} disabled={!canCreate}>
        mock-create-test-run
      </button>
    );
  };
});

jest.mock('@/components/common/RunDrawer', () => {
  return function MockRunDrawer({ open }: { open: boolean }) {
    return open ? <div data-testid="run-drawer" /> : null;
  };
});

describe('TestRunsPage', () => {
  it('passes canCreate through to the grid', () => {
    render(<TestRunsPage />);
    expect(screen.getByText('mock-create-test-run')).toBeEnabled();
  });

  it('opens the create drawer when the grid invokes onCreateClick', async () => {
    render(<TestRunsPage />);
    await userEvent.click(screen.getByText('mock-create-test-run'));
    expect(screen.getByTestId('run-drawer')).toBeInTheDocument();
  });
});
