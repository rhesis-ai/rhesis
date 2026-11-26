import React from 'react';
import { render, screen } from '@/test-utils';
import '@testing-library/jest-dom';
import ProtectedError from '../error';

jest.mock('next/navigation', () => ({
  usePathname: () => '/metrics/abc-123',
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
}));

const REACT_PLACEHOLDER =
  'Minified React error #441; visit https://react.dev/errors/441 for the full message';

describe('ProtectedError', () => {
  beforeEach(() => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("shows a plain message and a reference for a server error, never React's placeholder", () => {
    const error = Object.assign(new Error(REACT_PLACEHOLDER), {
      digest: '1947008980',
    });
    render(<ProtectedError error={error} reset={jest.fn()} />);

    expect(screen.getByText(/couldn't be loaded/)).toBeInTheDocument();
    expect(
      screen.getByText('Reference for support: 1947008980')
    ).toBeInTheDocument();
    expect(screen.queryByText(/Minified React error/)).not.toBeInTheDocument();
  });

  it('shows the message of an error thrown in the browser', () => {
    render(
      <ProtectedError error={new Error('Network down')} reset={jest.fn()} />
    );
    expect(screen.getByText('Network down')).toBeInTheDocument();
  });

  it('shows the access-denied page for a forbidden error from the browser', () => {
    const error = Object.assign(new Error('API error: 403 - Forbidden'), {
      status: 403,
    });
    render(<ProtectedError error={error} reset={jest.fn()} />);
    expect(
      screen.getByRole('heading', { name: 'Metrics — Access denied' })
    ).toBeInTheDocument();
  });
});
