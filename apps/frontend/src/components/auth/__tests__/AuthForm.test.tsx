import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import AuthForm, { oauthLoginUrl } from '../AuthForm';

jest.mock('next-auth/react', () => ({
  signIn: jest.fn(),
}));

jest.mock('@/utils/url-resolver', () => ({
  getBaseUrl: () => 'https://app.example.com/api/backend',
}));

import { signIn } from 'next-auth/react';

const makeProvidersResponse = (overrides: Record<string, unknown> = {}) => ({
  providers: [
    {
      name: 'email',
      display_name: 'Email',
      type: 'credentials',
      enabled: true,
      registration_enabled: true,
    },
    {
      name: 'google',
      display_name: 'Google',
      type: 'oauth',
      enabled: true,
    },
  ],
  password_policy: { min_length: 12, max_length: 128, min_strength_score: 2 },
  registration_enabled: true,
  ...overrides,
});

function mockFetch(
  body: unknown,
  status = 200,
  secondBody?: unknown,
  secondStatus = 200
) {
  const makeFetchResponse = (b: unknown, s: number) =>
    Promise.resolve({
      ok: s >= 200 && s < 300,
      status: s,
      json: () => Promise.resolve(b),
    } as unknown as Response);

  if (secondBody !== undefined) {
    (global.fetch as jest.Mock) = jest
      .fn()
      .mockResolvedValueOnce(makeFetchResponse(body, status))
      .mockResolvedValueOnce(makeFetchResponse(secondBody, secondStatus));
  } else {
    (global.fetch as jest.Mock) = jest
      .fn()
      .mockResolvedValue(makeFetchResponse(body, status));
  }
}

async function renderAndWaitForLoad(props: { isRegistration?: boolean } = {}) {
  mockFetch(makeProvidersResponse());
  render(<AuthForm {...props} />);
  await screen.findByRole('heading', {
    name: props.isRegistration ? 'Create your account' : 'Sign in',
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

/**
 * OAuth and SSO logins start on the same origin, through the BFF, so the
 * backend's handshake cookie lands on the frontend host.
 */
describe('oauthLoginUrl', () => {
  it('builds the provider login route under the BFF', () => {
    expect(oauthLoginUrl({ name: 'google' }, '/architect')).toBe(
      'https://app.example.com/api/backend/auth/login/google?return_to=%2Farchitect'
    );
  });

  it('keeps the BFF prefix for an absolute-path login_url (SSO)', () => {
    // `new URL('/auth/sso/acme', base)` would drop `/api/backend`.
    expect(
      oauthLoginUrl({ name: 'sso', login_url: '/auth/sso/acme' }, '/home')
    ).toBe(
      'https://app.example.com/api/backend/auth/sso/acme?return_to=%2Fhome'
    );
  });
});

describe('AuthForm — same-origin requests', () => {
  it('posts the email login to the BFF, not the API host', async () => {
    const user = userEvent.setup();
    mockFetch(makeProvidersResponse(), 200, { auth_code: 'c' });
    render(<AuthForm />);
    await screen.findByRole('heading', { name: 'Sign in' });

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.type(screen.getByLabelText(/^email/i), 'a@example.com');
    await user.type(
      screen.getByLabelText(/password/i, { selector: 'input' }),
      'correct horse battery'
    );
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        'https://app.example.com/api/backend/auth/login/email',
        expect.objectContaining({ method: 'POST' })
      )
    );
  });
});

describe('AuthForm — loading and error states', () => {
  it('shows a loading spinner while fetching providers', () => {
    (global.fetch as jest.Mock) = jest.fn(() => new Promise(() => {}));
    render(<AuthForm />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows an error alert when provider fetch fails', async () => {
    (global.fetch as jest.Mock) = jest
      .fn()
      .mockRejectedValue(new Error('Network error'));
    render(<AuthForm />);
    await screen.findByRole('alert');
    expect(
      screen.getByText(/failed to load authentication options/i)
    ).toBeInTheDocument();
  });
});

describe('AuthForm — login mode', () => {
  it('renders the login headline and primary buttons after loading', async () => {
    await renderAndWaitForLoad();
    expect(
      screen.getByRole('heading', { name: 'Sign in' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /continue with email/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /continue with google/i })
    ).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('expands the email/password form when "Continue with Email" is clicked', async () => {
    const user = userEvent.setup();
    await renderAndWaitForLoad();

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/password/i, { selector: 'input' })
    ).toBeInTheDocument();
  });

  it('shows the magic link form when "Email me a link" is clicked', async () => {
    const user = userEvent.setup();
    await renderAndWaitForLoad();

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.click(screen.getByText(/email me a link/i));

    expect(
      screen.getByText(/enter your email and we'll send you a link/i)
    ).toBeInTheDocument();
  });

  it('shows the confirmation screen after magic link is sent successfully', async () => {
    const user = userEvent.setup();

    (global.fetch as jest.Mock) = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(makeProvidersResponse()),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({}),
      } as unknown as Response);

    render(<AuthForm />);
    await screen.findByRole('heading', { name: 'Sign in' });

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.click(screen.getByText(/email me a link/i));
    await user.type(screen.getByLabelText(/^email/i), 'user@example.com');
    await user.click(screen.getByRole('button', { name: /email me a link/i }));

    await screen.findByText(/check your email/i);
    expect(
      screen.getByText(/we've sent a sign-in link to/i)
    ).toBeInTheDocument();
  });

  it('shows migration warning when password_not_set error code is returned', async () => {
    const user = userEvent.setup();

    (global.fetch as jest.Mock) = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(makeProvidersResponse()),
      } as unknown as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () =>
          Promise.resolve({
            detail: {
              error_code: 'password_not_set',
              message: 'No password set',
            },
          }),
      } as unknown as Response);

    render(<AuthForm />);
    await screen.findByRole('heading', { name: 'Sign in' });

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.type(screen.getByLabelText(/^email/i), 'migrated@example.com');
    await user.type(
      screen.getByLabelText(/password/i, { selector: 'input' }),
      'wrongpass'
    );
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await screen.findByText(/sign in with a link/i);
    expect(
      screen.getByText(/your account has been migrated/i)
    ).toBeInTheDocument();
    expect(signIn).not.toHaveBeenCalled();
  });
});

describe('AuthForm — registration mode', () => {
  it('renders the registration headline and name field', async () => {
    await renderAndWaitForLoad({ isRegistration: true });

    expect(
      screen.getByRole('heading', { name: 'Create your account' })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/^name/i)).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('shows a validation error when the password is too short', async () => {
    const user = userEvent.setup();
    await renderAndWaitForLoad({ isRegistration: true });

    await user.type(screen.getByLabelText(/^email/i), 'new@example.com');
    await user.type(
      screen.getByLabelText(/password/i, { selector: 'input' }),
      'short'
    );
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });
});

describe('AuthForm — registration disabled', () => {
  async function renderClosed(props: { isRegistration?: boolean } = {}) {
    mockFetch(makeProvidersResponse({ registration_enabled: false }));
    render(<AuthForm {...props} />);
    await screen.findByRole('heading', {
      name: props.isRegistration ? 'Create your account' : 'Sign in',
    });
  }

  it('hides "Create an account" on the sign-in form', async () => {
    const user = userEvent.setup();
    await renderClosed();

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );

    expect(
      screen.queryByRole('link', { name: /create an account/i })
    ).not.toBeInTheDocument();
  });

  it('replaces the register form with an invite-only notice', async () => {
    await renderClosed({ isRegistration: true });

    expect(screen.getByText(/sign-up is turned off/i)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /create account/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /continue with google/i })
    ).not.toBeInTheDocument();
  });

  it('still shows "Create an account" when sign-up is on', async () => {
    const user = userEvent.setup();
    await renderAndWaitForLoad();

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );

    expect(
      screen.getByRole('link', { name: /create an account/i })
    ).toBeInTheDocument();
  });
});
