import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import ChangePasswordDrawer from '../ChangePasswordDrawer';

jest.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: jest.fn() }),
}));
jest.mock('next-auth/react', () => ({
  signIn: jest.fn(),
  useSession: () => ({ update: jest.fn(), status: 'authenticated', data: {} }),
}));
jest.mock('@tanstack/react-query', () => ({
  ...jest.requireActual('@tanstack/react-query'),
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));
jest.mock('@/utils/api-client/auth-client', () => ({
  changePassword: jest.fn(),
}));
jest.mock('@/components/common/NotificationContext', () => ({
  useNotifications: () => ({ show: jest.fn() }),
}));
jest.mock('@/hooks/useIsAuthenticated', () => ({
  useUserScope: () => 'user-1',
}));

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({ ok: false }) as jest.Mock;
});

function renderDrawer() {
  render(<ChangePasswordDrawer open onClose={jest.fn()} hasPassword />);
}

describe('ChangePasswordDrawer field errors (WCAG 3.3.1)', () => {
  it('marks and focuses the new password when it is too short', async () => {
    renderDrawer();
    await userEvent.type(
      screen.getByLabelText('Current Password'),
      'old-pass-1'
    );
    await userEvent.type(screen.getByLabelText('New Password'), 'short');
    await userEvent.type(
      screen.getByLabelText('Confirm New Password'),
      'short'
    );

    await userEvent.click(
      screen.getByRole('button', { name: 'Change Password' })
    );

    const next = screen.getByLabelText('New Password');
    expect(next).toHaveAttribute('aria-invalid', 'true');
    expect(next).toHaveFocus();
    expect(next).not.toHaveAccessibleDescription(/^Minimum/);
    expect(screen.getByLabelText('Current Password')).toHaveAttribute(
      'aria-invalid',
      'false'
    );
  });

  it('marks the confirmation field when the passwords differ', async () => {
    renderDrawer();

    await userEvent.type(
      screen.getByLabelText('Current Password'),
      'old-pass-1'
    );
    await userEvent.type(
      screen.getByLabelText('New Password'),
      'Valid-pass-123!'
    );
    await userEvent.type(
      screen.getByLabelText('Confirm New Password'),
      'Different-456!'
    );
    await userEvent.click(
      screen.getByRole('button', { name: 'Change Password' })
    );

    const confirm = screen.getByLabelText('Confirm New Password');
    expect(confirm).toHaveAttribute('aria-invalid', 'true');
    expect(confirm).toHaveFocus();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
