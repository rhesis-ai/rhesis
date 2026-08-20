'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import ButtonBase from '@mui/material/ButtonBase';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import Typography from '@mui/material/Typography';
import { alpha } from '@mui/material/styles';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined';
import { FilterDrawerShell } from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Notification } from '@/utils/api-client/notifications-client';
import {
  NotificationSection,
  isNotificationSection,
} from '@/constants/notifications';
import { useNotifications } from '@/contexts/NotificationsContext';

const PAGE_SIZE = 30;

/** Tint on an unread row. Matches the grids' unread-row treatment in
 * `styles/globals.css` (`HIGHLIGHTED_ROW_CLASS`) rather than inventing a
 * second "this is unread" colour -- the same signal should look the same
 * wherever it appears. */
const UNREAD_ROW_TINT = 0.06;
/** Icon size for the empty state, matching the other empty states' glyph. */
const EMPTY_ICON_SIZE = 32;
/** Leading icon on a notification row. */
const ROW_ICON_SIZE = 20;

/** Where a row's own page lives, keyed by `NotificationSection`. Not always
 * `/${section}` -- `USAGE` badges no nav item (see `constants/notifications.ts`)
 * but a quota notification still needs somewhere to send the reader. */
const SECTION_ROUTES: Record<NotificationSection, string> = {
  [NotificationSection.TEST_SETS]: '/test-sets',
  [NotificationSection.TEST_RUNS]: '/test-runs',
  [NotificationSection.TASKS]: '/tasks',
  [NotificationSection.ARCHITECT]: '/architect',
  [NotificationSection.USAGE]: '/organizations/usage',
};

// Floors rather than rounds: 90 minutes is "1h ago", not "2h ago" -- an age
// must never read as further in the past than it is. Clamped at 0 so clock
// skew between server and browser cannot render "-1m ago".
function relativeTime(iso: string): string {
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - new Date(iso).getTime()) / 60_000)
  );
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function isSameDay(a: Date, b: Date): boolean {
  return a.toDateString() === b.toDateString();
}

function dayLabel(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  if (isSameDay(date, today)) return 'Today';
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (isSameDay(date, yesterday)) return 'Yesterday';
  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: date.getFullYear() === today.getFullYear() ? undefined : 'numeric',
  });
}

interface NotificationsDrawerProps {
  open: boolean;
  onClose: () => void;
}

/**
 * The notification center: full paginated history across every section,
 * day-grouped, with an unread-only toggle and mark-all-read. The sidebar
 * badge (`NavItem`, the brand-row usage badge) is a different, lighter
 * primitive (`NotificationsContext`'s per-section unread counts) -- this
 * drawer is the drill-down the router docstring on `GET /notifications/`
 * calls "a future notification drawer".
 */
export default function NotificationsDrawer({
  open,
  onClose,
}: NotificationsDrawerProps) {
  const router = useRouter();
  const { unreadBySection, markSectionRead, markOneRead } = useNotifications();
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [failed, setFailed] = useState(false);
  // Pages fetched so far. Deliberately not derived from `items.length`: rows
  // are marked read locally, and with the unread-only filter on that shrinks
  // the server-side list, so an offset taken from the rendered count steps
  // straight past unread rows it never showed.
  const [pagesLoaded, setPagesLoaded] = useState(0);

  const fetchPage = useCallback(
    async (page: number, replace: boolean) => {
      const client = new ApiClientFactory().getNotificationsClient();
      const rows = await client.getNotifications({
        unread_only: unreadOnly,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      // Dedupe on append: the list is ordered by `created_at desc` with no id
      // tiebreaker, so a notification arriving between pages shifts the
      // window and can re-serve a row already held -- which would also
      // duplicate a React key.
      setItems(prev => {
        if (replace) return rows;
        const seen = new Set(prev.map(n => n.id));
        return [...prev, ...rows.filter(n => !seen.has(n.id))];
      });
      setHasMore(rows.length === PAGE_SIZE);
      setPagesLoaded(page + 1);
    },
    [unreadOnly]
  );

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setFailed(false);
    fetchPage(0, true)
      .catch(() => {
        setItems([]);
        setFailed(true);
      })
      .finally(() => setLoading(false));
  }, [open, fetchPage]);

  const totalUnread = Object.values(unreadBySection).reduce(
    (sum, count) => sum + (count ?? 0),
    0
  );

  const handleMarkAllRead = () => {
    (Object.keys(unreadBySection) as NotificationSection[]).forEach(section => {
      if ((unreadBySection[section] ?? 0) > 0) markSectionRead(section);
    });
    setItems(prev =>
      prev.map(n =>
        n.read_at ? n : { ...n, read_at: new Date().toISOString() }
      )
    );
    // Everything shown is read now, so an unread-only list is empty and has
    // nothing older to offer.
    if (unreadOnly) setHasMore(false);
  };

  const handleRowClick = (notification: Notification) => {
    const section = isNotificationSection(notification.section)
      ? notification.section
      : null;
    if (!notification.read_at) {
      setItems(prev =>
        prev.map(n =>
          n.id === notification.id
            ? { ...n, read_at: new Date().toISOString() }
            : n
        )
      );
      // Through the context, not the client directly: it owns the badge count
      // and would otherwise keep counting a row the server has marked read.
      if (section) {
        markOneRead(section, notification.id, notification.item_count);
      }
    }
    onClose();
    if (section) router.push(SECTION_ROUTES[section]);
  };

  const handleLoadOlder = async () => {
    setLoadingMore(true);
    try {
      await fetchPage(pagesLoaded, false);
    } catch {
      setHasMore(false);
    } finally {
      setLoadingMore(false);
    }
  };

  const groups = useMemo(() => {
    const map = new Map<string, Notification[]>();
    for (const n of items) {
      const label = dayLabel(n.created_at);
      const list = map.get(label) ?? [];
      list.push(n);
      map.set(label, list);
    }
    return Array.from(map.entries());
  }, [items]);

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      title="Notifications"
      anchor="right"
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          flex: 1,
          minHeight: 0,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          {/* FormControlLabel rather than a hand-paired Switch and Typography:
              it associates the two, so the switch has a real accessible name
              and the text is clickable. */}
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={unreadOnly}
                onChange={e => setUnreadOnly(e.target.checked)}
              />
            }
            label="Unread only"
            slotProps={{
              typography: { variant: 'caption', color: 'text.secondary' },
            }}
          />
          <Button
            size="small"
            startIcon={<DoneAllIcon fontSize="small" />}
            onClick={handleMarkAllRead}
            disabled={totalUnread === 0}
          >
            Mark all read
          </Button>
        </Box>

        <Box
          sx={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress size={24} />
            </Box>
          ) : failed ? (
            // Distinct from the empty state: "no notifications yet" would
            // read as good news when the request actually failed.
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <Typography variant="body2" color="error.main">
                Could not load notifications. Please try again later.
              </Typography>
            </Box>
          ) : items.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <NotificationsNoneOutlinedIcon
                sx={{ fontSize: EMPTY_ICON_SIZE, color: 'text.secondary' }}
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {unreadOnly ? "You're all caught up" : 'No notifications yet'}
              </Typography>
            </Box>
          ) : (
            groups.map(([label, rows]) => (
              <Box key={label}>
                <Typography
                  variant="caption"
                  sx={{ px: '4px', color: 'text.secondary', fontWeight: 600 }}
                >
                  {label}
                </Typography>
                {rows.map(n => (
                  <ButtonBase
                    key={n.id}
                    onClick={() => handleRowClick(n)}
                    sx={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      textAlign: 'left',
                      width: '100%',
                      gap: '10px',
                      px: '10px',
                      py: '8px',
                      borderRadius: BORDER_RADIUS.sm,
                      bgcolor: n.read_at
                        ? 'transparent'
                        : theme =>
                            alpha(theme.palette.primary.main, UNREAD_ROW_TINT),
                      '&:hover': {
                        bgcolor: theme => theme.palette.greyscale.surface2,
                      },
                    }}
                  >
                    {n.is_failure ? (
                      <ErrorOutlineIcon
                        sx={{
                          fontSize: ROW_ICON_SIZE,
                          color: 'error.main',
                          flexShrink: 0,
                          mt: '2px',
                        }}
                      />
                    ) : (
                      <NotificationsNoneOutlinedIcon
                        sx={{
                          fontSize: ROW_ICON_SIZE,
                          color: 'text.secondary',
                          flexShrink: 0,
                          mt: '2px',
                        }}
                      />
                    )}
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        variant="body2"
                        sx={{ fontWeight: n.read_at ? 400 : 600 }}
                      >
                        {n.title}
                        {n.item_count > 1 ? ` (${n.item_count})` : ''}
                      </Typography>
                      {n.body && (
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          component="div"
                        >
                          {n.body}
                        </Typography>
                      )}
                    </Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ flexShrink: 0, whiteSpace: 'nowrap' }}
                    >
                      {relativeTime(n.created_at)}
                    </Typography>
                  </ButtonBase>
                ))}
              </Box>
            ))
          )}
          {hasMore && items.length > 0 && (
            <Button
              size="small"
              onClick={handleLoadOlder}
              disabled={loadingMore}
              sx={{ alignSelf: 'center', mt: 1 }}
            >
              {loadingMore ? 'Loading…' : 'Load older'}
            </Button>
          )}
        </Box>
      </Box>
    </FilterDrawerShell>
  );
}
