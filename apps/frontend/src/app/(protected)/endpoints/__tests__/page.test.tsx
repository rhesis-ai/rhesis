import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import EndpointsPage from '../page';

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    refresh: jest.fn(),
  }),
  usePathname: () => '/endpoints',
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

// EndpointsGrid owns the query and the loading/empty/populated decision
// itself — the page's only job is to wire `canCreate` and `onCreateClick`
// through to it correctly.
jest.mock('../components/EndpointsGrid', () => {
  return function MockEndpointsGrid({
    canCreate,
    onCreateClick,
  }: {
    canCreate?: boolean;
    onCreateClick?: () => void;
  }) {
    return (
      <button onClick={onCreateClick} disabled={!canCreate}>
        mock-create-endpoint
      </button>
    );
  };
});

jest.mock('../components/EndpointCreateDrawer', () => {
  return function MockEndpointCreateDrawer({ open }: { open: boolean }) {
    return open ? <div data-testid="endpoint-create-drawer" /> : null;
  };
});

describe('EndpointsPage', () => {
  it('passes canCreate through to the grid', () => {
    render(<EndpointsPage />);
    expect(screen.getByText('mock-create-endpoint')).toBeEnabled();
  });

  it('opens the create drawer when the grid invokes onCreateClick', async () => {
    render(<EndpointsPage />);
    await userEvent.click(screen.getByText('mock-create-endpoint'));
    expect(screen.getByTestId('endpoint-create-drawer')).toBeInTheDocument();
  });
});
