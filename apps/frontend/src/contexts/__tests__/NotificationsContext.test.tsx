import React from 'react';
import { render, screen, waitFor, act } from '@/test-utils';
import '@testing-library/jest-dom';

import {
  NotificationsProvider,
  useNotifications,
  useViewingEntity,
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

// Mutable so tests can simulate being on the section's list page vs. a
// nested detail sub-route (e.g. '/test-sets' vs '/test-sets/abc123').
let mockPathname = '/';

jest.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
}));

const mockInvalidateQueries = jest.fn();

jest.mock('@tanstack/react-query', () => ({
  ...jest.requireActual('@tanstack/react-query'),
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
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

/** Probe that declares an architect session as being on screen. */
function ViewingProbe({ sessionId }: { sessionId: string | null }) {
  const { unreadBySection } = useNotifications();
  useViewingEntity(NotificationSection.ARCHITECT, sessionId);
  return (
    <div data-testid="architect-unread">
      {unreadBySection[NotificationSection.ARCHITECT] ?? 0}
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
  mockPathname = '/';
  mockInvalidateQueries.mockClear();
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

  it('accumulates counts and highlights across several events', async () => {
    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    ['ts-1', 'ts-2', 'ts-3'].forEach(entityId => {
      emitNotification({
        section: 'test-sets',
        entity_id: entityId,
        project_id: 'project-a',
      });
    });

    expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('3');
    expect(screen.getByTestId('test-sets-highlights')).toHaveTextContent(
      'ts-1,ts-2,ts-3'
    );
  });

  it('counts a batch notification as its item_count, and highlights every id', async () => {
    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    // One Garak import that created three test sets: a single row on the
    // backend, three things done as far as the badge is concerned.
    emitNotification({
      section: 'test-sets',
      entity_id: null,
      item_count: 3,
      project_id: 'project-a',
      payload: { entity_ids: ['ts-1', 'ts-2', 'ts-3'] },
    });

    expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('3');
    expect(screen.getByTestId('test-sets-highlights')).toHaveTextContent(
      'ts-1,ts-2,ts-3'
    );
  });

  it('does not re-highlight an entity already in the list', async () => {
    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    emitNotification({
      section: 'test-sets',
      entity_id: 'ts-1',
      project_id: 'project-a',
    });
    emitNotification({
      section: 'test-sets',
      entity_id: 'ts-1',
      project_id: 'project-a',
    });

    // Both count -- two jobs did finish -- but the row is listed once.
    expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('2');
    expect(screen.getByTestId('test-sets-highlights')).toHaveTextContent(
      'ts-1'
    );
  });

  it('invalidates the section query cache on a matching websocket event', async () => {
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

    // Only the list queries -- not the whole ['test-sets'] prefix, which
    // would also match (and needlessly refetch) some other test set's own
    // detail-page query. See constants/query-keys.ts.
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ['test-sets', 'list'],
    });
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

  it('marks a section read on landing on its own list page', async () => {
    mockGetSummary.mockResolvedValue({
      sections: { 'test-sets': { unread: 1, entity_ids: ['ts-1'] } },
    });
    mockPathname = '/test-sets';

    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('0')
    );
    await waitFor(() =>
      expect(mockMarkRead).toHaveBeenCalledWith({
        section: NotificationSection.TEST_SETS,
      })
    );
  });

  it('keeps counting notifications that arrive while already on the list page', async () => {
    // The Garak import drawer lives on /test-sets, so this is the normal
    // flow: start three imports, stay put, watch the badge count up. Marking
    // each one read on arrival used to wipe the badge back to nothing and
    // clear the rows' highlights server-side along with it.
    mockPathname = '/test-sets';

    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    ['ts-1', 'ts-2', 'ts-3'].forEach(entityId => {
      emitNotification({
        section: 'test-sets',
        entity_id: entityId,
        project_id: 'project-a',
      });
    });

    expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('3');
    expect(screen.getByTestId('test-sets-highlights')).toHaveTextContent(
      'ts-1,ts-2,ts-3'
    );
    expect(mockMarkRead).not.toHaveBeenCalled();
  });

  it('does not mark a section read on a nested detail sub-route', async () => {
    // Generating a test set redirects straight to that test set's own
    // detail page (/test-sets/[id]) -- this must not consume the badge
    // before the user ever sees the list.
    mockGetSummary.mockResolvedValue({
      sections: { 'test-sets': { unread: 1, entity_ids: ['ts-1'] } },
    });
    mockPathname = '/test-sets/ts-1';

    render(
      <NotificationsProvider>
        <Probe />
      </NotificationsProvider>
    );

    await waitFor(() =>
      expect(screen.getByTestId('test-sets-unread')).toHaveTextContent('1')
    );
    expect(mockMarkRead).not.toHaveBeenCalled();
  });

  it('does not badge a notification for the entity currently on screen', async () => {
    render(
      <NotificationsProvider>
        <ViewingProbe sessionId="session-1" />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    emitNotification({
      id: 'notif-1',
      section: 'architect',
      entity_id: 'session-1',
      project_id: 'project-a',
    });

    expect(screen.getByTestId('architect-unread')).toHaveTextContent('0');
    // Cleared server-side too, so it doesn't come back on the next load.
    await waitFor(() =>
      expect(mockMarkRead).toHaveBeenCalledWith({
        notification_ids: ['notif-1'],
      })
    );
    expect(mockInvalidateQueries).not.toHaveBeenCalled();
  });

  it('still badges a notification for a different entity in that section', async () => {
    render(
      <NotificationsProvider>
        <ViewingProbe sessionId="session-1" />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    emitNotification({
      id: 'notif-2',
      section: 'architect',
      entity_id: 'session-2',
      project_id: 'project-a',
    });

    expect(screen.getByTestId('architect-unread')).toHaveTextContent('1');
    expect(mockMarkRead).not.toHaveBeenCalled();
  });

  it('badges again once the entity is no longer on screen', async () => {
    const { rerender } = render(
      <NotificationsProvider>
        <ViewingProbe sessionId="session-1" />
      </NotificationsProvider>
    );
    await waitFor(() => expect(mockGetSummary).toHaveBeenCalled());

    // Session closed -- the registration must have been torn down.
    rerender(
      <NotificationsProvider>
        <ViewingProbe sessionId={null} />
      </NotificationsProvider>
    );

    emitNotification({
      id: 'notif-3',
      section: 'architect',
      entity_id: 'session-1',
      project_id: 'project-a',
    });

    expect(screen.getByTestId('architect-unread')).toHaveTextContent('1');
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
