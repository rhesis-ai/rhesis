import React from 'react';
import { render, screen, waitFor, act } from '@/test-utils';
import '@testing-library/jest-dom';

import {
  NotificationsProvider,
  useNotifications,
} from '../NotificationsContext';
import { NotificationSection } from '@/constants/notifications';
import type { EventHandler } from '@/utils/websocket';

const mockGetSummary = jest.fn();
const mockMarkRead = jest.fn();

let capturedHandler: EventHandler | null = null;
const mockUnsubscribe = jest.fn();
const mockSubscribe = jest.fn((_eventType: unknown, handler: EventHandler) => {
  capturedHandler = handler;
  return mockUnsubscribe;
});

jest.mock('../WebSocketContext', () => ({
  // isConnected: true so the subscribe effect registers immediately -- the
  // real parent/child effect-ordering seam is covered by
  // NotificationsWebSocketWiring.test.tsx, which uses the real provider.
  useWebSocketContext: () => ({ subscribe: mockSubscribe, isConnected: true }),
}));

// The provider skips fetching without an organization (onboarding users have
// none and the endpoint 403s), so every test here needs one. Mutable so the
// onboarding case can drop it.
let mockSessionUser: { id: string; organization_id?: string | null } = {
  id: 'user-1',
  organization_id: 'org-1',
};

jest.mock('next-auth/react', () => ({
  useSession: () => ({
    data: { user: mockSessionUser },
    status: 'authenticated',
  }),
}));

// Mutable so individual tests can simulate switching the active project,
// matching the `mockSession` pattern in FeaturesContext.test.tsx.
let mockActiveProject: { id: string } | null = { id: 'project-a' };

jest.mock('../ActiveProjectContext', () => ({
  useActiveProject: () => ({ activeProject: mockActiveProject }),
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
  const { unreadBySection, highlightedIds, markSectionRead } =
    useNotifications();
  return (
    <div>
      <div data-testid="test-sets-unread">
        {unreadBySection[NotificationSection.TEST_SETS] ?? 0}
      </div>
      <div data-testid="test-sets-highlights">
        {highlightedIds(NotificationSection.TEST_SETS).join(',')}
      </div>
      <button onClick={() => markSectionRead(NotificationSection.TEST_SETS)}>
        mark read
      </button>
    </div>
  );
}

function emitNotification(payload: Record<string, unknown>) {
  act(() => {
    capturedHandler?.({ type: 'notification', payload });
  });
}

beforeEach(() => {
  mockGetSummary.mockReset().mockResolvedValue({ sections: {} });
  mockMarkRead.mockReset().mockResolvedValue({ updated: 1 });
  mockSubscribe.mockClear();
  mockUnsubscribe.mockClear();
  capturedHandler = null;
  mockActiveProject = { id: 'project-a' };
  mockSessionUser = { id: 'user-1', organization_id: 'org-1' };
});

describe('NotificationsProvider', () => {
  it('fetches the summary on mount and exposes unread counts', async () => {
    mockGetSummary.mockResolvedValue({
      sections: { 'test-sets': { unread: 2, entity_ids: ['ts-1'] } },
    });

    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('2')
    );
    expect(screen.getByTestId('test-sets-highlights')).toHaveTextContent(
      'ts-1'
    );
  });

  it('increments unread count and highlights on a matching websocket event', async () => {
    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    emitNotification({
      section: 'test-sets',
      entity_id: 'ts-2',
      project_id: 'project-a',
    });

    expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('1');
    expect(screen.getByTestId('test-sets-highlights')).toHaveTextContent(
      'ts-2'
    );
  });

  it('ignores a websocket event scoped to a different project', async () => {
    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    emitNotification({
      section: 'test-sets',
      entity_id: 'ts-2',
      project_id: 'project-b',
    });

    expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('0');
  });

  it('an org-wide event (no project_id) is not filtered out', async () => {
    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    emitNotification({ section: 'test-runs', entity_id: 'tr-1' });

    // test-sets stays at 0; the event was for a different section, this just
    // confirms an event with no project_id isn't dropped by the project guard.
    expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('0');
  });

  it('markSectionRead zeroes the count and calls the mark-read endpoint', async () => {
    mockGetSummary.mockResolvedValue({
      sections: { 'test-sets': { unread: 3, entity_ids: [] } },
    });

    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );
    await waitFor(() =>
      expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('3')
    );

    act(() => {
      screen.getByText('mark read').click();
    });

    expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('0');
    await waitFor(() =>
      expect(mockMarkRead).toHaveBeenCalledWith({
        section: NotificationSection.TEST_SETS,
      })
    );
  });

  it('refetches the summary when the active project changes', async () => {
    const { rerender } = render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalledTimes(1));

    mockActiveProject = { id: 'project-b' };
    rerender(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );

    await waitFor(() => expect(mockGetSummary).toHaveBeenCalledTimes(2));
  });

  it('does not fetch while the user has no organization (onboarding)', async () => {
    mockSessionUser = { id: 'user-1', organization_id: null };

    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );

    // Give any effect a chance to fire before asserting the negative.
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockGetSummary).not.toHaveBeenCalled();
    expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('0');
  });
});
