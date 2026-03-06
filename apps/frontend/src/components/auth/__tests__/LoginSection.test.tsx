import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import LoginSection from '../LoginSection';

// LoginSection is a thin wrapper around AuthForm — mock AuthForm to keep these
// tests focused on the section's own props and layout.
jest.mock('../AuthForm', () => ({
  __esModule: true,
  default: ({ isRegistration }: { isRegistration?: boolean }) => (
    <div
      data-testid="auth-form"
      data-is-registration={String(isRegistration ?? false)}
    />
  ),
}));

describe('LoginSection', () => {
  it('renders an AuthForm by default', () => {
    render(<LoginSection />);
    expect(screen.getByTestId('auth-form')).toBeInTheDocument();
  });

  it('passes isRegistration=false by default', () => {
    render(<LoginSection />);
    expect(screen.getByTestId('auth-form')).toHaveAttribute(
      'data-is-registration',
      'false'
    );
  });

  it('passes isRegistration=true when the prop is provided', () => {
    render(<LoginSection isRegistration />);
    expect(screen.getByTestId('auth-form')).toHaveAttribute(
      'data-is-registration',
      'true'
    );
  });

  it('renders with a Box wrapper around the AuthForm', () => {
    const { container } = render(<LoginSection />);
    // The component wraps in nested Box elements; verify the auth-form is inside
    const authForm = screen.getByTestId('auth-form');
    expect(container.firstChild).toContainElement(authForm);
  });
});
