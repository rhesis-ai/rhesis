import React from 'react';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { NotificationProvider, useNotifications } from '../NotificationContext';
import { LiveAnnouncerProvider } from '../LiveAnnouncer';

const TOAST = { selector: '.MuiAlert-message' };

// Test component that uses the notification hook
function TestConsumer() {
  const { show, close } = useNotifications();

  return (
    <div>
      <button onClick={() => show('Success!', { severity: 'success' })}>
        Show Success
      </button>
      <button onClick={() => show('Error!', { severity: 'error' })}>
        Show Error
      </button>
      <button
        onClick={() => {
          const key = show('Closeable', { key: 'test-key' });
          // Store key for closing
          (window as unknown as Record<string, unknown>).__notifKey = key;
        }}
      >
        Show Closeable
      </button>
      <button
        onClick={() => {
          const key = (window as unknown as Record<string, unknown>).__notifKey;
          if (key) close(key as string);
        }}
      >
        Close Notification
      </button>
    </div>
  );
}

describe('NotificationProvider', () => {
  it('renders children', () => {
    render(
      <NotificationProvider>
        <div>Child content</div>
      </NotificationProvider>
    );

    expect(screen.getByText('Child content')).toBeInTheDocument();
  });

  it('shows notification when show is called', async () => {
    render(
      <NotificationProvider>
        <TestConsumer />
      </NotificationProvider>
    );

    await act(async () => {
      screen.getByText('Show Success').click();
    });

    expect(screen.getByText('Success!')).toBeInTheDocument();
  });

  it('shows error notification', async () => {
    render(
      <NotificationProvider>
        <TestConsumer />
      </NotificationProvider>
    );

    await act(async () => {
      screen.getByText('Show Error').click();
    });

    expect(screen.getByText('Error!')).toBeInTheDocument();
  });

  describe('timing (WCAG 2.2.1)', () => {
    beforeEach(() => jest.useFakeTimers());
    afterEach(() => jest.useRealTimers());

    it('keeps an error until it is dismissed, announced at once', async () => {
      render(
        <LiveAnnouncerProvider>
          <NotificationProvider>
            <TestConsumer />
          </NotificationProvider>
        </LiveAnnouncerProvider>
      );

      await act(async () => {
        screen.getByText('Show Error').click();
      });
      await act(async () => {
        jest.advanceTimersByTime(60_000);
      });

      expect(screen.getByText('Error!', TOAST)).toBeInTheDocument();
      expect(
        screen.getByText('Error!', { selector: '[aria-live="assertive"]' })
      ).toBeInTheDocument();
    });

    it('lets a success message go after a few seconds, announced politely', async () => {
      render(
        <LiveAnnouncerProvider>
          <NotificationProvider>
            <TestConsumer />
          </NotificationProvider>
        </LiveAnnouncerProvider>
      );

      await act(async () => {
        screen.getByText('Show Success').click();
      });
      await act(async () => {
        jest.advanceTimersByTime(200);
      });
      // Read from the always-present live region, not the new toast element.
      expect(screen.getByRole('status')).toHaveTextContent('Success!');

      // Auto-hide, then the exit transition.
      await act(async () => {
        jest.advanceTimersByTime(10_000);
      });
      await act(async () => {
        jest.advanceTimersByTime(1_000);
      });

      expect(screen.queryByText('Success!', TOAST)).not.toBeInTheDocument();
    });
  });
});

describe('useNotifications', () => {
  it('throws when used outside provider', () => {
    // Suppress React error boundary output
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});

    function BadConsumer() {
      useNotifications();
      return null;
    }

    expect(() => render(<BadConsumer />)).toThrow(
      'useNotifications must be used within a NotificationProvider'
    );

    spy.mockRestore();
  });
});
