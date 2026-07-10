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

function createFetchResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as unknown as Response);
}

function setupFetchMock(
  options: {
    termsAccepted?: boolean;
    onFetch?: (
      url: string,
      init?: RequestInit
    ) => { body: unknown; status?: number } | null;
  } = {}
) {
  const { termsAccepted = false, onFetch } = options;
  (global.fetch as jest.Mock) = jest.fn(
    (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (onFetch) {
        const override = onFetch(url, init);
        if (override) {
          return createFetchResponse(override.body, override.status ?? 200);
        }
      }
      if (url.includes('/auth/terms-status')) {
        return createFetchResponse({ terms_accepted: termsAccepted });
      }
      if (url.includes('/api/auth-config')) {
        return createFetchResponse(makeProvidersResponse());
      }
      return createFetchResponse({});
    }
  );
}

function mockFetch(
  body: unknown,
  status = 200,
  secondBody?: unknown,
  secondStatus = 200
) {
  if (secondBody !== undefined) {
    let callCount = 0;
    setupFetchMock({
      onFetch: (url, init) => {
        if (url.includes('/api/auth-config')) {
          return { body, status };
        }
        if (init?.method === 'POST') {
          callCount += 1;
          if (callCount === 1) {
            return { body: secondBody, status: secondStatus };
          }
        }
        return null;
      },
    });
  } else {
    setupFetchMock({
      onFetch: url => {
        if (url.includes('/api/auth-config')) {
          return { body, status };
        }
        return null;
      },
    });
  }
}

async function renderAndWaitForLoad(
  props: { isRegistration?: boolean } = {},
  fetchOptions: Parameters<typeof setupFetchMock>[0] = {}
) {
  setupFetchMock(fetchOptions);
  render(<AuthForm {...props} />);
  await screen.findByText(
    props.isRegistration ? 'Create your account' : 'Welcome'
  );
}

beforeEach(() => {
  jest.clearAllMocks();
});

afterEach(() => {
  jest.useRealTimers();
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

  it('shows a T&C warning when submitting without accepting terms', async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    await renderAndWaitForLoad();

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.type(screen.getByLabelText(/^email/i), 'user@example.com');
    await jest.advanceTimersByTimeAsync(500);
    await user.type(
      screen.getByLabelText(/password/i, { selector: 'input' }),
      'mypassword'
    );
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(
      screen.getByText(/please accept the terms and conditions/i)
    ).toBeInTheDocument();
    expect(signIn).not.toHaveBeenCalled();
    jest.useRealTimers();
  });

  it('hides the T&C checkbox when the user already accepted terms', async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    await renderAndWaitForLoad({}, { termsAccepted: true });

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.type(screen.getByLabelText(/^email/i), 'user@example.com');
    await jest.advanceTimersByTimeAsync(500);

    expect(
      await screen.findByText(/by continuing, you confirm your agreement/i)
    ).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    jest.useRealTimers();
  });

  it('removes T&C warning after the checkbox is ticked', async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
    await renderAndWaitForLoad();

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.type(screen.getByLabelText(/^email/i), 'user@example.com');
    await jest.advanceTimersByTimeAsync(500);
    await user.type(
      screen.getByLabelText(/password/i, { selector: 'input' }),
      'mypassword'
    );
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(
      screen.getByText(/please accept the terms and conditions/i)
    ).toBeInTheDocument();

    await user.click(screen.getByRole('checkbox'));

    expect(
      screen.queryByText(/please accept the terms and conditions/i)
    ).not.toBeInTheDocument();
    jest.useRealTimers();
  });

  it('shows T&C warning when clicking an OAuth button without accepting terms', async () => {
    const user = userEvent.setup();
    await renderAndWaitForLoad();

    await user.click(
      screen.getByRole('button', { name: /continue with google/i })
    );

    expect(
      screen.getByText(/please accept the terms and conditions/i)
    ).toBeInTheDocument();
    // OAuth redirect should NOT have happened (signIn was not called)
    expect(signIn).not.toHaveBeenCalled();
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
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

    setupFetchMock({
      onFetch: (url, init) => {
        if (url.includes('/auth/magic-link') && init?.method === 'POST') {
          return { body: { success: true } };
        }
        return null;
      },
    });

    render(<AuthForm />);
    await screen.findByText('Welcome');

    await user.click(screen.getByRole('checkbox'));
    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.click(screen.getByText(/email me a link/i));
    await user.type(screen.getByLabelText(/^email/i), 'user@example.com');
    await jest.advanceTimersByTimeAsync(500);
    await user.click(screen.getByRole('button', { name: /email me a link/i }));

    await screen.findByText(/check your email/i);
    expect(
      screen.getByText(/we've sent a sign-in link to/i)
    ).toBeInTheDocument();
    jest.useRealTimers();
  });

  it('shows an error when the magic link request fails', async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

    setupFetchMock({
      onFetch: (url, init) => {
        if (url.includes('/auth/magic-link') && init?.method === 'POST') {
          return { body: { detail: 'User not found' }, status: 400 };
        }
        return null;
      },
    });

    render(<AuthForm />);
    await screen.findByText('Welcome');

    await user.click(screen.getByRole('checkbox'));
    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.click(screen.getByText(/email me a link/i));
    await user.type(screen.getByLabelText(/^email/i), 'user@example.com');
    await jest.advanceTimersByTimeAsync(500);
    await user.click(screen.getByRole('button', { name: /email me a link/i }));

    await screen.findByRole('alert');
    expect(screen.getByText('User not found')).toBeInTheDocument();
    jest.useRealTimers();
  });

  it('shows migration warning when password_not_set error code is returned', async () => {
    jest.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

    setupFetchMock({
      onFetch: (url, init) => {
        if (url.includes('/auth/login/email') && init?.method === 'POST') {
          return {
            body: {
              detail: {
                error_code: 'password_not_set',
                message: 'No password set',
              },
            },
            status: 401,
          };
        }
        return null;
      },
    });

    render(<AuthForm />);
    await screen.findByText('Welcome');

    await user.click(screen.getByRole('checkbox'));
    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.type(screen.getByLabelText(/^email/i), 'migrated@example.com');
    await jest.advanceTimersByTimeAsync(500);
    await user.type(
      screen.getByLabelText(/password/i, { selector: 'input' }),
      'wrongpass'
    );
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await screen.findByText(/sign in with a link/i);
    expect(
      screen.getByText(/your account has been migrated/i)
    ).toBeInTheDocument();
    jest.useRealTimers();
  });

  it('shows "Back to all sign-in options" when email form is active', async () => {
    const user = userEvent.setup();
    await renderAndWaitForLoad();

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );

    expect(
      screen.getByRole('button', { name: /back to all sign-in options/i })
    ).toBeInTheDocument();
  });

  it('collapses the email form when "Back" button is clicked', async () => {
    const user = userEvent.setup();
    await renderAndWaitForLoad();

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );
    await user.click(
      screen.getByRole('button', { name: /back to all sign-in options/i })
    );

    expect(screen.queryByLabelText(/^email/i)).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /continue with email/i })
    ).toBeInTheDocument();
  });

  it('toggles password visibility when the eye icon is clicked', async () => {
    const user = userEvent.setup();
    await renderAndWaitForLoad();

    await user.click(
      screen.getByRole('button', { name: /continue with email/i })
    );

    const passwordInput = screen.getByLabelText(/password/i, {
      selector: 'input',
    });
    expect(passwordInput).toHaveAttribute('type', 'password');

    await user.click(
      screen.getByRole('button', { name: /toggle password visibility/i })
    );
    expect(passwordInput).toHaveAttribute('type', 'text');

    await user.click(
      screen.getByRole('button', { name: /toggle password visibility/i })
    );
    expect(passwordInput).toHaveAttribute('type', 'password');
  });
});

describe('AuthForm — registration mode', () => {
  it('renders the registration headline and name field', async () => {
    await renderAndWaitForLoad({ isRegistration: true });

    expect(screen.getByText('Create your account')).toBeInTheDocument();
    expect(screen.getByLabelText(/^name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^email/i)).toBeInTheDocument();
    expect(
      screen.getByLabelText(/password/i, { selector: 'input' })
    ).toBeInTheDocument();
  });

  it('shows password minimum length helper text', async () => {
    await renderAndWaitForLoad({ isRegistration: true });
    expect(screen.getByText(/minimum 12 characters/i)).toBeInTheDocument();
  });

  it('shows a validation error when the password is too short', async () => {
    const user = userEvent.setup();
    await renderAndWaitForLoad({ isRegistration: true });

    await user.click(screen.getByRole('checkbox'));
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

  it('shows "Already have an account?" link', async () => {
    await renderAndWaitForLoad({ isRegistration: true });
    expect(screen.getByText(/already have an account/i)).toBeInTheDocument();
  });
});
