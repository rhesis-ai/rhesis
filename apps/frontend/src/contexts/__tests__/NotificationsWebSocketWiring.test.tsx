/**
 * Integration test for the NotificationsProvider <-> WebSocketProvider seam.
 *
 * NotificationsContext.test.tsx mocks `useWebSocketContext` wholesale, so it
 * cannot catch a wiring failure between the two providers. This test uses the
 * REAL WebSocketProvider and mocks only the low-level WebSocketClient, so the
 * effect-ordering contract between parent and child is actually exercised:
 * React flushes child effects before parent effects, and the parent is what
 * populates the client ref that `subscribe` needs.
 */
import React from 'react';
import { render, screen, waitFor, act } from '@/test-utils';
import '@testing-library/jest-dom';

import { WebSocketProvider } from '../WebSocketContext';
import {
  NotificationsProvider,
  useNotifications,
} from '../NotificationsContext';
import { NotificationSection } from '@/constants/notifications';
import { EventType, type EventHandler } from '@/utils/websocket';

const mockGetSummary = jest.fn();
const mockMarkRead = jest.fn();

// Handlers registered on the fake client, by event type.
const registered = new Map<string, EventHandler>();
let connectionChangeCb: ((connected: boolean) => void) | undefined;

const mockClientSubscribe = jest.fn(
  (eventType: string, handler: EventHandler) => {
    registered.set(eventType, handler);
    return () => registered.delete(eventType);
  }
);

jest.mock('@/utils/websocket', () => {
  const actual = jest.requireActual('@/utils/websocket');
  return {
    ...actual,
    WebSocketClient: jest.fn().mockImplementation((options: unknown) => {
      connectionChangeCb = (
        options as { onConnectionChange?: (c: boolean) => void }
      ).onConnectionChange;
      return {
        // Starts disconnected, like a real socket mid-handshake.
        isConnected: false,
        connectionId: undefined,
        connect: jest.fn(),
        disconnect: jest.fn(),
        subscribe: mockClientSubscribe,
        subscribeToChannel: jest.fn(),
        unsubscribeFromChannel: jest.fn(),
        reconnect: jest.fn(),
        send: jest.fn(),
      };
    }),
  };
});

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: { id: 'user-1', organization_id: 'org-1' } },
    status: 'authenticated',
  }),
}));

jest.mock('../ActiveProjectContext', () => ({
  useActiveProject: () => ({ activeProject: { id: 'project-a' } }),
}));

jest.mock('@/utils/api-client/websocket-token-client', () => ({
  WebSocketTokenClient: jest.fn().mockImplementation(() => ({
    getWebSocketToken: jest.fn().mockResolvedValue({ token: 'ws-token' }),
  })),
}));

jest.mock('@/utils/api-client/client-factory', () => ({
  ApiClientFactory: jest.fn().mockImplementation(() => ({
    getNotificationsClient: () => ({
      getSummary: mockGetSummary,
      markRead: mockMarkRead,
    }),
  })),
}));

function Probe() {
  const { unreadBySection } = useNotifications();
  return (
    <div data-testid="unread">
      {unreadBySection[NotificationSection.TEST_SETS] ?? 0}
    </div>
  );
}

beforeEach(() => {
  mockGetSummary.mockReset().mockResolvedValue({ sections: {} });
  mockMarkRead.mockReset().mockResolvedValue({ updated: 1 });
  mockClientSubscribe.mockClear();
  registered.clear();
  connectionChangeCb = undefined;
});

// One test rather than two: `WebSocketContext` keeps its client in
// module-level state that survives unmount (deliberately, to dedupe tokens
// across a Strict Mode remount), so a second render in this file reuses the
// first client and never re-runs the constructor this mock hooks. Splitting
// the assertions would be testing that singleton's lifecycle, not the wiring.
describe('NotificationsProvider websocket wiring', () => {
  it('registers a NOTIFICATION handler once connected and delivers events to the badge', async () => {
    render(
      <WebSocketProvider>
        <NotificationsProvider>
          <Probe />
        </NotificationsProvider>
      </WebSocketProvider>
    );

    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    // The socket finishes its handshake after mount, as a real one does.
    // Before this point `subscribe` is a no-op (the parent effect that
    // populates the client ref has not run when the child effect fires).
    act(() => {
      connectionChangeCb?.(true);
    });

    await waitFor(() =>
      expect(registered.has(EventType.NOTIFICATION)).toBe(true)
    );

    act(() => {
      registered.get(EventType.NOTIFICATION)?.({
        type: EventType.NOTIFICATION,
        payload: {
          section: NotificationSection.TEST_SETS,
          entity_id: 'ts-1',
          project_id: 'project-a',
        },
      });
    });

    expect(screen.getByTestId('unread')).toHaveTextContent('1');
  });
});
