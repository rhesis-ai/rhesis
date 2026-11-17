import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import VerificationBanner, { verificationMessage } from '../VerificationBanner';

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

  it('has no dismiss button, since the account locks if unverified', () => {
    mockSession({ email: 'user@example.com', is_email_verified: false });
    render(<VerificationBanner />);
    expect(
      screen.queryByRole('button', { name: /dismiss/i })
    ).not.toBeInTheDocument();
  });

  it('shows the days left before the account locks', () => {
    const dueAt = new Date(
      Date.now() + 2.5 * 24 * 60 * 60 * 1000
    ).toISOString();
    mockSession({
      email: 'user@example.com',
      is_email_verified: false,
      email_verification_due_at: dueAt,
    });
    render(<VerificationBanner />);
    expect(screen.getByText(/within 3 days/i)).toBeInTheDocument();
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

describe('verificationMessage', () => {
  const now = Date.parse('2026-11-16T12:00:00Z');

  it('falls back to the plain message without a deadline', () => {
    expect(verificationMessage(null, now)).toMatch(/please verify/i);
  });

  it('says "today" on the last day', () => {
    expect(verificationMessage('2026-11-17T06:00:00Z', now)).toMatch(/today/i);
  });

  it('counts whole days left', () => {
    expect(verificationMessage('2026-11-19T12:00:00Z', now)).toMatch(
      /within 3 days/i
    );
  });
});
