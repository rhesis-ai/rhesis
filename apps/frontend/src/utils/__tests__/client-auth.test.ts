import { clearAllSessionData } from '../session';
import { signOut } from 'next-auth/react';
import { handleClientSignOut } from '../client-auth';

jest.mock('../session', () => ({
  clearAllSessionData: jest.fn(),
}));

jest.mock('next-auth/react', () => ({
  signOut: jest.fn(),
}));

beforeEach(() => {
  jest.clearAllMocks();
  (clearAllSessionData as jest.Mock).mockResolvedValue(undefined);
  (signOut as jest.Mock).mockResolvedValue(undefined);
});

describe('handleClientSignOut', () => {
  it('calls clearAllSessionData before calling signOut', async () => {
    const callOrder: string[] = [];
    (clearAllSessionData as jest.Mock).mockImplementation(async () => {
      callOrder.push('clearAllSessionData');
    });
    (signOut as jest.Mock).mockImplementation(async () => {
      callOrder.push('signOut');
    });

    await handleClientSignOut();

    expect(callOrder).toEqual(['clearAllSessionData', 'signOut']);
  });

  it('calls signOut with the correct redirect callback URL', async () => {
    await handleClientSignOut();

    expect(signOut).toHaveBeenCalledWith({
      redirect: true,
      callbackUrl: '/?session_expired=true&force_logout=true',
    });
  });

  it('does not re-throw when signOut throws an error (catches and redirects)', async () => {
    (signOut as jest.Mock).mockRejectedValue(new Error('signOut failed'));

    // The catch block performs a fallback redirect; the function must not propagate the error.
    await expect(handleClientSignOut()).resolves.toBeUndefined();
  });

  it('does not re-throw when clearAllSessionData throws an error (catches and redirects)', async () => {
    (clearAllSessionData as jest.Mock).mockRejectedValue(
      new Error('session clear failed')
    );

    await expect(handleClientSignOut()).resolves.toBeUndefined();
  });

  it('prevents concurrent sign-out calls (mutex flag)', async () => {
    let resolveSession!: (value?: unknown) => void;
    (clearAllSessionData as jest.Mock).mockImplementation(
      () =>
        new Promise(resolve => {
          resolveSession = resolve;
        })
    );

    // Start first call (hangs waiting for clearAllSessionData)
    const promise1 = handleClientSignOut();
    // Start second call immediately — mutex should block it
    const promise2 = handleClientSignOut();

    // Release the first call
    resolveSession();
    await Promise.all([promise1, promise2]);

    // clearAllSessionData should only have been called once
    expect(clearAllSessionData).toHaveBeenCalledTimes(1);
  });
});
