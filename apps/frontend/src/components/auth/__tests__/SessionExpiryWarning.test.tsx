import React from 'react';
import { act, render, screen, fireEvent } from '@testing-library/react';
import SessionExpiryWarning, {
  SESSION_WARNING_LEAD_MS,
} from '../SessionExpiryWarning';

const mockUpdate = jest.fn();
let mockExpires: string | undefined;

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: mockExpires ? { expires: mockExpires } : null,
    status: 'authenticated',
    update: mockUpdate,
  }),
}));

jest.mock('@/actions/auth', () => ({ handleSignOut: jest.fn() }));

describe('SessionExpiryWarning', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2026-01-01T12:00:00Z'));
    mockUpdate.mockReset();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('stays hidden while the session has plenty of time left', () => {
    mockExpires = new Date(Date.now() + 60 * 60 * 1000).toISOString();
    render(<SessionExpiryWarning />);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('warns shortly before the session ends', () => {
    mockExpires = new Date(
      Date.now() + SESSION_WARNING_LEAD_MS + 15_000
    ).toISOString();
    render(<SessionExpiryWarning />);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(20_000);
    });

    expect(screen.getByRole('alertdialog')).toHaveAccessibleName(
      'Your session is about to end'
    );
    expect(
      screen.getByRole('button', { name: 'Stay signed in' })
    ).toHaveFocus();
  });

  it('extends the session when the user asks to stay', async () => {
    mockExpires = new Date(Date.now() + 60_000).toISOString();
    mockUpdate.mockResolvedValue({ expires: 'later' });
    render(<SessionExpiryWarning />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Stay signed in' }));
    });

    expect(mockUpdate).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('says so when the session cannot be extended', async () => {
    mockExpires = new Date(Date.now() + 60_000).toISOString();
    mockUpdate.mockResolvedValue(null);
    render(<SessionExpiryWarning />);

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Stay signed in' }));
    });

    expect(screen.getByRole('alert')).toHaveTextContent("couldn't be extended");
  });
});
