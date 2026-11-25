import React from 'react';
import { render, screen } from '@testing-library/react';
import SSOErrorPage from '../page';

let query = '';
jest.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(query),
}));
jest.mock('@/components/auth/AuthPageShell', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
jest.mock('@/components/auth/useAuthStyles', () => ({
  useAuthStyles: () => ({ heading: {}, primaryButton: {} }),
}));

describe('SSO error page', () => {
  it('explains a known reason', () => {
    query = 'error=not_invited';
    render(<SSOErrorPage />);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Ask your administrator to invite you'
    );
  });

  it('falls back to a generic message for unknown codes', () => {
    query = 'error=toString';
    render(<SSOErrorPage />);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Something went wrong while signing you in'
    );
  });

  it('shows the reference for the administrator', () => {
    query = 'error=login_failed&ref=abc123';
    render(<SSOErrorPage />);
    expect(screen.getByText('abc123')).toBeInTheDocument();
  });

  it('links back to sign in', () => {
    query = '';
    render(<SSOErrorPage />);
    expect(
      screen.getByRole('link', { name: 'Back to sign in' })
    ).toHaveAttribute('href', '/');
  });
});
