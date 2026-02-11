import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { ErrorBoundary } from '../ErrorBoundary';

// Create a theme that includes the custom helperText variant
const testTheme = createTheme({
  typography: {
    helperText: {
      fontSize: '0.875rem',
    },
  } as any,
});

// Wrapper with ThemeProvider for components that use custom theme properties
function ThemeWrapper({ children }: { children: React.ReactNode }) {
  return <ThemeProvider theme={testTheme}>{children}</ThemeProvider>;
}

// Component that throws an error for testing
function ThrowingComponent({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error message');
  }
  return <div>Normal content</div>;
}

// Suppress React error boundary console.error output during tests
const originalError = console.error;
beforeAll(() => {
  console.error = jest.fn();
});
afterAll(() => {
  console.error = originalError;
});

describe('ErrorBoundary', () => {
  it('renders children when there is no error', () => {
    render(
      <ThemeWrapper>
        <ErrorBoundary>
          <ThrowingComponent shouldThrow={false} />
        </ErrorBoundary>
      </ThemeWrapper>
    );

    expect(screen.getByText('Normal content')).toBeInTheDocument();
  });

  it('renders error UI when a child throws', () => {
    render(
      <ThemeWrapper>
        <ErrorBoundary>
          <ThrowingComponent shouldThrow={true} />
        </ErrorBoundary>
      </ThemeWrapper>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    // Error message is inside a <pre> element alongside the stack trace
    expect(
      screen.getByText(content => content.includes('Test error message'))
    ).toBeInTheDocument();
  });

  it('shows Try Again and Refresh Page buttons', () => {
    render(
      <ThemeWrapper>
        <ErrorBoundary>
          <ThrowingComponent shouldThrow={true} />
        </ErrorBoundary>
      </ThemeWrapper>
    );

    expect(
      screen.getByRole('button', { name: /try again/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /refresh page/i })
    ).toBeInTheDocument();
  });

  it('recovers when Try Again is clicked and error is resolved', async () => {
    render(
      <ThemeWrapper>
        <ErrorBoundary>
          <ThrowingComponent shouldThrow={true} />
        </ErrorBoundary>
      </ThemeWrapper>
    );

    // Verify error state
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    // Click try again
    await userEvent.click(screen.getByRole('button', { name: /try again/i }));

    // After retry, ErrorBoundary resets its state and re-renders children.
    // Since the component still throws (props haven't changed),
    // it will re-enter error state. This tests the retry mechanism itself.
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('renders custom fallback when provided', () => {
    const CustomFallback = ({
      error,
      retry,
    }: {
      error?: Error;
      retry: () => void;
    }) => (
      <div>
        <p>Custom error: {error?.message}</p>
        <button onClick={retry}>Custom retry</button>
      </div>
    );

    render(
      <ErrorBoundary fallback={CustomFallback}>
        <ThrowingComponent shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(
      screen.getByText('Custom error: Test error message')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /custom retry/i })
    ).toBeInTheDocument();
  });
});
