'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { usePathname } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useQueryClient } from '@tanstack/react-query';
import { EventType } from '@/utils/websocket';
import { useWebSocketContext } from './WebSocketContext';
import { useActiveProject } from './ActiveProjectContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { NotificationSection } from '@/constants/notifications';

type SectionCounts = Partial<Record<NotificationSection, number>>;
type SectionHighlights = Partial<Record<NotificationSection, string[]>>;

interface NotificationEventPayload {
  id?: string;
  section?: string;
  entity_id?: string | null;
  project_id?: string | null;
  payload?: { entity_ids?: string[] } | null;
}

interface NotificationsContextValue {
  /** Unread count per section, for the sidebar badge. */
  unreadBySection: SectionCounts;
  /** Entity ids to gently highlight in a section's grid. */
  highlightedIds: (section: NotificationSection) => string[];
  /** Zero a section's badge and persist read_at on the backend. */
  markSectionRead: (section: NotificationSection) => void;
  /** Drop one id from a section's highlight list (e.g. on row click). */
  clearHighlight: (section: NotificationSection, id: string) => void;
  /**
   * Declare that this entity is on screen right now, so its own notifications
   * are pointless. Returns an unregister function. Prefer the
   * `useViewingEntity` hook over calling this directly.
   */
  registerViewing: (
    section: NotificationSection,
    entityId: string
  ) => () => void;
}

// Default (no provider in the tree) is "no notifications", not a thrown
// error -- NavItem reads this deep in the nav tree, and unit tests that
// render NavItem/NavSection/Sidebar in isolation should not need to wrap
// every render in a NotificationsProvider, matching how PermissionsContext's
// ambient default behaves.
const defaultNotificationsContext: NotificationsContextValue = {
  unreadBySection: {},
  highlightedIds: () => [],
  markSectionRead: () => {},
  clearHighlight: () => {},
  registerViewing: () => () => {},
};

const NotificationsContext = createContext<NotificationsContextValue>(
  defaultNotificationsContext
);

const SECTION_VALUES: string[] = Object.values(NotificationSection);

function isNotificationSection(value: string): value is NotificationSection {
  return SECTION_VALUES.includes(value);
}

/**
 * Tracks per-section unread counts and highlightable entity ids for the
 * sidebar badge and grid row highlight.
 *
 * Not to be confused with `components/common/NotificationContext`'s
 * `NotificationProvider` (singular) -- that one is the generic toast/snackbar
 * system. This is the persistent, backend-tracked "a background job
 * finished" badge.
 *
 * Refetches `/notifications/summary` on mount and whenever the active
 * project changes -- the summary is project-scoped (see
 * `apps/backend/AGENTS.md`'s "Ambient Request Scope"), and the highlight
 * list is fully replaced on that refetch, which is what resets a highlight
 * left over from a different project's rows.
 */
export function NotificationsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { subscribe, isConnected } = useWebSocketContext();
  const { activeProject } = useActiveProject();
  const pathname = usePathname();
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  // The endpoints resolve tenant context from the caller's org and 403 without
  // one, so a user still in onboarding has nothing to fetch -- skip rather than
  // fire a request on every onboarding page load that can only fail.
  const hasOrganization = Boolean(
    (session?.user as { organization_id?: string | null } | undefined)
      ?.organization_id
  );

  const [unreadBySection, setUnreadBySection] = useState<SectionCounts>({});
  const [highlighted, setHighlighted] = useState<SectionHighlights>({});
  // "section:entityId" for every entity currently on screen. A ref, not
  // state: the websocket handler reads it, and re-running that effect on
  // every navigation would churn the subscription for no benefit.
  const viewingRef = useRef<Set<string>>(new Set());

  const registerViewing = useCallback(
    (section: NotificationSection, entityId: string) => {
      const key = `${section}:${entityId}`;
      viewingRef.current.add(key);
      return () => {
        viewingRef.current.delete(key);
      };
    },
    []
  );

  const markIdsRead = useCallback((notificationIds: string[]) => {
    new ApiClientFactory()
      .getNotificationsClient()
      .markRead({ notification_ids: notificationIds })
      .catch(error => {
        console.warn('Failed to mark notifications read:', error);
      });
  }, []);

  const fetchSummary = useCallback(async () => {
    try {
      const client = new ApiClientFactory().getNotificationsClient();
      const { sections } = await client.getSummary();
      const nextUnread: SectionCounts = {};
      const nextHighlighted: SectionHighlights = {};
      Object.entries(sections).forEach(([section, summary]) => {
        if (!isNotificationSection(section) || !summary) return;
        nextUnread[section] = summary.unread;
        nextHighlighted[section] = summary.entity_ids;
      });
      setUnreadBySection(nextUnread);
      setHighlighted(nextHighlighted);
    } catch (error) {
      console.warn('Failed to fetch notification summary:', error);
    }
    // Project scoping is server-side via the active-project cookie, not an
    // explicit dependency here -- the effect below re-runs this on project change.
  }, []);

  useEffect(() => {
    if (!hasOrganization) return;
    fetchSummary();
  }, [hasOrganization, activeProject?.id, fetchSummary]);

  useEffect(() => {
    const unsubscribe = subscribe(EventType.NOTIFICATION, message => {
      const payload = message.payload as NotificationEventPayload | undefined;
      if (!payload?.section || !isNotificationSection(payload.section)) return;

      // A websocket event reaches every tab the user has open, regardless
      // of which project that tab is viewing -- UserTarget delivery has no
      // project concept. Ignore an event scoped to a different project
      // than the one this tab is currently showing.
      if (payload.project_id && payload.project_id !== activeProject?.id) {
        return;
      }

      const section = payload.section;

      // The user is looking at this exact entity, so telling them about it is
      // pointless -- the page showing it live is responsible for its own
      // updates (the architect page streams its session over a channel, for
      // instance). Mark the row read straight away so it doesn't resurface on
      // the next load, and skip the badge, the highlight and the list
      // invalidation. Note this is per-entity: a notification for a *different*
      // architect session still badges normally.
      const entityId = payload.entity_id ? String(payload.entity_id) : null;
      if (entityId && viewingRef.current.has(`${section}:${entityId}`)) {
        if (payload.id) markIdsRead([String(payload.id)]);
        return;
      }

      setUnreadBySection(prev => ({
        ...prev,
        [section]: (prev[section] ?? 0) + 1,
      }));

      // Invalidate only the section's *list* queries (e.g. testSetKeys.list()
      // === ['test-sets', 'list', ...], see constants/query-keys.ts), not
      // the whole ['test-sets'] prefix -- that would also match a test
      // set's own detail-page query (testSetKeys.detail(id), whose key is
      // ['test-sets', 'detail', id, ...]) and force it to refetch too,
      // flickering an unrelated test set's page every time any test set's
      // list changes. Refetches a currently-mounted grid immediately and
      // marks it stale for its next mount, so a newly created row shows up
      // without a manual page reload.
      queryClient.invalidateQueries({ queryKey: [section, 'list'] });

      const newIds = [
        ...(payload.entity_id ? [payload.entity_id] : []),
        ...(payload.payload?.entity_ids ?? []),
      ];
      if (newIds.length > 0) {
        setHighlighted(prev => ({
          ...prev,
          [section]: [...(prev[section] ?? []), ...newIds],
        }));
      }
    });
    return unsubscribe;
    // `isConnected` is a required dependency, not decoration: React flushes
    // child effects before parent effects, so on first commit
    // WebSocketProvider has not yet populated the ref that `subscribe` reads,
    // and `subscribe` silently returns a no-op unsubscribe. `subscribe` itself
    // has a stable identity, so without re-running when the socket comes up
    // the handler would never be registered at all.
  }, [subscribe, isConnected, activeProject?.id, queryClient, markIdsRead]);

  const markSectionRead = useCallback((section: NotificationSection) => {
    setUnreadBySection(prev => {
      if (!prev[section]) return prev;
      return { ...prev, [section]: 0 };
    });
    new ApiClientFactory()
      .getNotificationsClient()
      .markRead({ section })
      .catch(error => {
        console.warn('Failed to mark notifications read:', error);
      });
  }, []);

  // Visiting a section's own list page clears its badge. Fires again on a
  // later render if a new notification for the current section arrives
  // while already here -- unreadBySection[section] going back above 0
  // re-triggers the effect.
  //
  // Must be the exact list route, not just a matching first path segment --
  // e.g. generating a test set redirects straight to that new test set's
  // *detail* page (/test-sets/[id]), which shares the 'test-sets' segment
  // with the list page. Matching on the segment alone marked the section
  // read before the user ever saw the list, which (since /notifications/
  // summary only returns entity_ids for still-unread rows) also erased the
  // row's highlight on a later reload, before it had ever been shown.
  useEffect(() => {
    const segment = pathname?.split('/')[1];
    if (!segment || !isNotificationSection(segment)) return;
    if (pathname !== `/${segment}`) return;
    if ((unreadBySection[segment] ?? 0) > 0) {
      markSectionRead(segment);
    }
  }, [pathname, unreadBySection, markSectionRead]);

  const clearHighlight = useCallback(
    (section: NotificationSection, id: string) => {
      setHighlighted(prev => {
        const ids = prev[section];
        if (!ids || !ids.includes(id)) return prev;
        return { ...prev, [section]: ids.filter(existing => existing !== id) };
      });
    },
    []
  );

  const highlightedIds = useCallback(
    (section: NotificationSection) => highlighted[section] ?? [],
    [highlighted]
  );

  const value: NotificationsContextValue = {
    unreadBySection,
    highlightedIds,
    markSectionRead,
    clearHighlight,
    registerViewing,
  };

  return (
    <NotificationsContext.Provider value={value}>
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications(): NotificationsContextValue {
  return useContext(NotificationsContext);
}

/**
 * Suppress notifications for the entity this component is currently showing.
 *
 * For a page that already streams its own live updates, a badge for the thing
 * on screen is noise. While mounted with a non-null `entityId`, a matching
 * notification is marked read on arrival instead of badged. Pass null when
 * nothing is open (e.g. no architect session selected) to suppress nothing.
 */
export function useViewingEntity(
  section: NotificationSection,
  entityId: string | null | undefined
): void {
  const { registerViewing } = useNotifications();
  useEffect(() => {
    if (!entityId) return;
    return registerViewing(section, entityId);
  }, [registerViewing, section, entityId]);
}
