import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import AuthForm from '../AuthForm';

jest.mock('next-auth/react', () => ({
  signIn: jest.fn(),
}));

jest.mock('@/utils/url-resolver', () => ({
  getClientApiBaseUrl: () => 'http://127.0.0.1:8080/api/v1',
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
  await screen.findByText(
    props.isRegistration ? 'Create your account' : 'Welcome'
  );
}

beforeEach(() => {
  jest.clearAllMocks();
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
    expect(screen.getByText('Welcome')).toBeInTheDocument();
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
    await screen.findByText('Welcome');

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
    await screen.findByText('Welcome');

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

    expect(screen.getByText('Create your account')).toBeInTheDocument();
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
