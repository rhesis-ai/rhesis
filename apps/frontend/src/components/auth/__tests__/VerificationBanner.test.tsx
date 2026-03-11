import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import VerificationBanner from '../VerificationBanner';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

jest.mock('@/utils/url-resolver', () => ({
  getClientApiBaseUrl: () => 'http://127.0.0.1:8080/api/v1',
}));

import { useSession } from 'next-auth/react';

function mockSession(user: Record<string, unknown> | null = null) {
  (useSession as jest.Mock).mockReturnValue({
    data: user ? { user } : null,
  });
}

function makeFetchResponse(status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve({}),
  } as unknown as Response);
}

beforeEach(() => {
  (global.fetch as jest.Mock) = jest
    .fn()
    .mockResolvedValue(makeFetchResponse());
});

afterEach(() => {
  jest.clearAllMocks();
});

describe('VerificationBanner', () => {
  it('renders nothing when user is already verified', () => {
    mockSession({ email: 'user@example.com', is_email_verified: true });
    const { container } = render(<VerificationBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when there is no session', () => {
    mockSession(null);
    const { container } = render(<VerificationBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when user has no email', () => {
    mockSession({ is_email_verified: false });
    const { container } = render(<VerificationBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the verification banner for an unverified user', () => {
    mockSession({ email: 'user@example.com', is_email_verified: false });
    render(<VerificationBanner />);
    expect(
      screen.getByText(/please verify your email address/i)
    ).toBeInTheDocument();
  });

  it('renders the Resend button when not yet resent', () => {
    mockSession({ email: 'user@example.com', is_email_verified: false });
    render(<VerificationBanner />);
    expect(screen.getByRole('button', { name: /resend/i })).toBeInTheDocument();
  });

  it('sends a POST to the resend-verification endpoint when Resend is clicked', async () => {
    const user = userEvent.setup();
    mockSession({ email: 'user@example.com', is_email_verified: false });
    render(<VerificationBanner />);

    await user.click(screen.getByRole('button', { name: /resend/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8080/api/v1/auth/resend-verification',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ email: 'user@example.com' }),
        })
      );
    });
  });

  it('shows "Verification email sent!" after successful resend', async () => {
    const user = userEvent.setup();
    mockSession({ email: 'user@example.com', is_email_verified: false });
    render(<VerificationBanner />);

    await user.click(screen.getByRole('button', { name: /resend/i }));

    await screen.findByText(/verification email sent/i);
    expect(
      screen.queryByRole('button', { name: /resend/i })
    ).not.toBeInTheDocument();
  });

  it('shows a spinner while the resend request is in-flight', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock) = jest.fn(() => new Promise(() => {}));
    mockSession({ email: 'user@example.com', is_email_verified: false });
    render(<VerificationBanner />);

    await user.click(screen.getByRole('button', { name: /resend/i }));

    expect(screen.getByRole('button', { name: /resend/i })).toBeDisabled();
    expect(document.querySelector('[role="progressbar"]')).toBeInTheDocument();
  });

  it('dismisses the banner when the close button is clicked', async () => {
    const user = userEvent.setup();
    mockSession({ email: 'user@example.com', is_email_verified: false });
    render(<VerificationBanner />);

    expect(
      screen.getByText(/please verify your email address/i)
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /dismiss banner/i }));

    expect(
      screen.queryByText(/please verify your email address/i)
    ).not.toBeInTheDocument();
  });

  it('silently continues if the resend request fails', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock) = jest
      .fn()
      .mockRejectedValue(new Error('Network error'));
    mockSession({ email: 'user@example.com', is_email_verified: false });
    render(<VerificationBanner />);

    await user.click(screen.getByRole('button', { name: /resend/i }));

    // After the error, the banner should still show (no crash)
    await waitFor(() => {
      expect(
        screen.getByText(/please verify your email address/i)
      ).toBeInTheDocument();
    });
  });

  it('treats unset is_email_verified as verified (defaults to true)', () => {
    // If is_email_verified is not set, default is true, so banner should NOT show
    mockSession({ email: 'user@example.com' });
    const { container } = render(<VerificationBanner />);
    expect(container).toBeEmptyDOMElement();
  });
});
