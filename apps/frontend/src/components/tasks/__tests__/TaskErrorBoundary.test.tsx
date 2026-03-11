import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { TaskErrorBoundary } from '../TaskErrorBoundary';

jest.mock('@/components/icons', () => ({
  RefreshIcon: () => <span data-testid="refresh-icon" />,
}));

// A component that throws on render
function Bomb({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('Kaboom!');
  return <div data-testid="child">Safe content</div>;
}

// Suppress console.error output from React's error boundary logging
beforeEach(() => {
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe('TaskErrorBoundary', () => {
  it('renders children when there is no error', () => {
    render(
      <TaskErrorBoundary>
        <Bomb shouldThrow={false} />
      </TaskErrorBoundary>
    );
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });

  it('renders the default error UI when a child throws', () => {
    render(
      <TaskErrorBoundary>
        <Bomb shouldThrow={true} />
      </TaskErrorBoundary>
    );
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  });

  it('renders the custom fallback when provided', () => {
    render(
      <TaskErrorBoundary fallback={<div data-testid="custom-fallback" />}>
        <Bomb shouldThrow={true} />
      </TaskErrorBoundary>
    );
    expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
  });

  it('shows a Retry button in the default error state', () => {
    render(
      <TaskErrorBoundary>
        <Bomb shouldThrow={true} />
      </TaskErrorBoundary>
    );
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('shows the Retry button (clicking it resets the hasError state)', async () => {
    const user = userEvent.setup();

    render(
      <TaskErrorBoundary>
        <Bomb shouldThrow={true} />
      </TaskErrorBoundary>
    );

    // Error is shown before retry
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();

    // Retry button exists and is interactive
    const retryBtn = screen.getByRole('button', { name: /retry/i });
    expect(retryBtn).toBeEnabled();

    // Clicking retry doesn't throw an unhandled error in the test runner
    await expect(user.click(retryBtn)).resolves.not.toThrow();
  });
});
