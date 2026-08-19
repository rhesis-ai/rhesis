'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Box from '@mui/material/Box';
import ButtonBase from '@mui/material/ButtonBase';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';
import { alpha } from '@mui/material/styles';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined';
import { FilterDrawerShell } from '@/components/common/FilterDrawer';
import { BORDER_RADIUS } from '@/styles/theme';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type { Notification } from '@/utils/api-client/notifications-client';
import { NotificationSection } from '@/constants/notifications';
import { useNotifications } from '@/contexts/NotificationsContext';

const PAGE_SIZE = 30;

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

const SECTION_VALUES: string[] = Object.values(NotificationSection);

function isNotificationSection(value: string): value is NotificationSection {
  return SECTION_VALUES.includes(value);
}

function relativeTime(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
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
  const { unreadBySection, markSectionRead } = useNotifications();
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const fetchPage = useCallback(
    async (skip: number, replace: boolean) => {
      const client = new ApiClientFactory().getNotificationsClient();
      const page = await client.getNotifications({
        unread_only: unreadOnly,
        skip,
        limit: PAGE_SIZE,
      });
      setItems(prev => (replace ? page : [...prev, ...page]));
      setHasMore(page.length === PAGE_SIZE);
    },
    [unreadOnly]
  );

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetchPage(0, true)
      .catch(() => setItems([]))
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
  };

  const handleRowClick = (notification: Notification) => {
    if (!notification.read_at) {
      setItems(prev =>
        prev.map(n =>
          n.id === notification.id
            ? { ...n, read_at: new Date().toISOString() }
            : n
        )
      );
      new ApiClientFactory()
        .getNotificationsClient()
        .markRead({ notification_ids: [notification.id] })
        .catch(() => {
          // Best-effort -- the row already reads as read locally.
        });
    }
    onClose();
    if (isNotificationSection(notification.section)) {
      router.push(SECTION_ROUTES[notification.section]);
    }
  };

  const handleLoadOlder = async () => {
    setLoadingMore(true);
    try {
      await fetchPage(items.length, false);
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
          <Box sx={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Switch
              size="small"
              checked={unreadOnly}
              onChange={e => setUnreadOnly(e.target.checked)}
              inputProps={{ 'aria-label': 'Show unread only' }}
            />
            <Typography variant="caption" color="text.secondary">
              Unread only
            </Typography>
          </Box>
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
          ) : items.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <NotificationsNoneOutlinedIcon
                sx={{ fontSize: 32, color: 'text.secondary' }}
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
                        : theme => alpha(theme.palette.primary.main, 0.06),
                      '&:hover': {
                        bgcolor: theme => theme.palette.greyscale.surface2,
                      },
                    }}
                  >
                    {n.is_failure ? (
                      <ErrorOutlineIcon
                        sx={{
                          fontSize: 20,
                          color: 'error.main',
                          flexShrink: 0,
                          mt: '2px',
                        }}
                      />
                    ) : (
                      <NotificationsNoneOutlinedIcon
                        sx={{
                          fontSize: 20,
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
