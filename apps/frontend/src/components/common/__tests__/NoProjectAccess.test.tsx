import React from 'react';
import { render, screen } from '@testing-library/react';
import NoProjectAccess from '../NoProjectAccess';

const mockPush = jest.fn();
let mockCanCreate = true;

jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock('@/components/common/Can', () => ({
  useCan: () => mockCanCreate,
  useCanWithStatus: () => ({ allowed: mockCanCreate, loading: false }),
  Can: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  can: () => mockCanCreate,
}));

jest.mock('@/contexts/ActiveProjectContext', () => ({
  useActiveProject: () => ({ refresh: jest.fn() }),
}));

jest.mock('@/components/navigation/ProjectSwitcherDrawer', () => ({
  __esModule: true,
  default: () => null,
}));

describe('NoProjectAccess', () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockCanCreate = true;
  });

  it('offers project creation when the user holds project:create', () => {
    render(<NoProjectAccess />);

    expect(
      screen.getByRole('button', { name: /create a new project/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/or create a new one/i)).toBeInTheDocument();
  });

  // The built-in Member role does not hold project:create (it is org-scoped),
  // so SSO-provisioned users land here without it. Offering the button anyway
  // sent them into the wizard, which only failed with a 403 on submit.
  it('hides project creation when the user lacks project:create', () => {
    mockCanCreate = false;

    render(<NoProjectAccess />);

    expect(
      screen.queryByRole('button', { name: /create a new project/i })
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/or create a new one/i)).not.toBeInTheDocument();
  });

  it('always offers the re-check action', () => {
    mockCanCreate = false;

    render(<NoProjectAccess />);

    expect(
      screen.getByRole('button', { name: /check again/i })
    ).toBeInTheDocument();
  });
});
