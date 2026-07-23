import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TasksPage from '../page';

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    refresh: jest.fn(),
  }),
  usePathname: () => '/tasks',
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

// TasksGrid owns the query and the loading/empty/populated decision itself —
// the page's only job is to wire `canCreate`/`onCreateClick` through to it.
jest.mock('../components/TasksGrid', () => {
  return function MockTasksGrid({
    canCreate,
    onCreateClick,
  }: {
    canCreate?: boolean;
    onCreateClick?: () => void;
  }) {
    return (
      <button onClick={onCreateClick} disabled={!canCreate}>
        mock-create-task
      </button>
    );
  };
});

jest.mock('../components/TaskDrawer', () => {
  return function MockTaskDrawer({ open }: { open: boolean }) {
    return open ? <div data-testid="task-drawer" /> : null;
  };
});

describe('TasksPage', () => {
  it('passes canCreate through to the grid', () => {
    render(<TasksPage />);
    expect(screen.getByText('mock-create-task')).toBeEnabled();
  });

  it('opens the create drawer when the grid invokes onCreateClick', async () => {
    render(<TasksPage />);
    await userEvent.click(screen.getByText('mock-create-task'));
    expect(screen.getByTestId('task-drawer')).toBeInTheDocument();
  });
});
