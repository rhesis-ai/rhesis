import React from 'react';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { NotificationProvider, useNotifications } from '../NotificationContext';

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
          (window as any).__notifKey = key;
        }}
      >
        Show Closeable
      </button>
      <button
        onClick={() => {
          const key = (window as any).__notifKey;
          if (key) close(key);
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
