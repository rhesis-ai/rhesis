import * as React from 'react';
import { Snackbar, Alert, useTheme } from '@mui/material';
import { useAnnounce } from './LiveAnnouncer';

export type NotificationSeverity =
  | 'success'
  | 'info'
  | 'warning'
  | 'error'
  | 'neutral';

interface NotificationOptions {
  severity?: NotificationSeverity;
  autoHideDuration?: number;
  key?: string;
}

interface NotificationItem {
  message: string;
  options: NotificationOptions;
  key: string;
}

interface NotificationContextType {
  show: (message: string, options?: NotificationOptions) => string;
  close: (key: string) => void;
}

const NotificationContext = React.createContext<
  NotificationContextType | undefined
>(undefined);

let notificationCount = 0;

// Errors and warnings stay until dismissed: a message that vanishes after a
// few seconds is a time limit the user can't adjust (WCAG 2.2.1).
const PERSISTENT_SEVERITIES = new Set<NotificationSeverity>([
  'error',
  'warning',
]);
const DEFAULT_AUTO_HIDE_MS = 6000;

export function NotificationProvider({
  children,
  anchorOrigin = { vertical: 'top', horizontal: 'right' },
}: {
  children: React.ReactNode;
  anchorOrigin?: { vertical: 'top' | 'bottom'; horizontal: 'left' | 'right' };
}) {
  const [notifications, setNotifications] = React.useState<NotificationItem[]>(
    []
  );
  const [open, setOpen] = React.useState(false);
  const [currentNotification, setCurrentNotification] = React.useState<
    NotificationItem | undefined
  >(undefined);
  const theme = useTheme();
  const announce = useAnnounce();

  // Use refs for values accessed by stable callbacks to avoid
  // recreating show/close on every state change, which would cause
  // consumers' useEffects to re-fire and potentially infinite loop.
  const currentNotificationRef = React.useRef(currentNotification);
  React.useEffect(() => {
    currentNotificationRef.current = currentNotification;
  }, [currentNotification]);

  // Track active notification keys synchronously via ref so duplicate
  // detection in show() works reliably under React concurrent rendering
  // (state updaters may be deferred, but ref mutations are immediate).
  const activeKeysRef = React.useRef(new Set<string>());

  React.useEffect(() => {
    if (notifications.length && !currentNotification) {
      // Set a new notification when we don't have an active one
      setCurrentNotification({ ...notifications[0] });
      setNotifications(prev => prev.slice(1));
      setOpen(true);
    } else if (notifications.length && currentNotification && open) {
      // Close an active notification when a new one is added
      setOpen(false);
    }
  }, [notifications, currentNotification, open]);

  const show = React.useCallback(
    (message: string, options: NotificationOptions = {}) => {
      const key = options.key || `notification-${++notificationCount}`;

      // Synchronous duplicate check via ref — immune to React's
      // deferred state scheduling under concurrent rendering.
      if (options.key && activeKeysRef.current.has(options.key)) {
        return key;
      }

      activeKeysRef.current.add(key);
      setNotifications(prev => [...prev, { message, options, key }]);
      // The toast's own element is brand new, so screen readers skip it.
      announce(
        message,
        PERSISTENT_SEVERITIES.has(options.severity ?? 'info')
          ? 'assertive'
          : 'polite'
      );

      return key;
    },
    [announce]
  );

  const close = React.useCallback((key: string) => {
    activeKeysRef.current.delete(key);
    if (currentNotificationRef.current?.key === key) {
      setOpen(false);
    } else {
      setNotifications(prev =>
        prev.filter(notification => notification.key !== key)
      );
    }
  }, []);

  const handleClose = (_event?: unknown, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpen(false);
  };

  const handleExited = React.useCallback(() => {
    const key = currentNotificationRef.current?.key;
    if (key) activeKeysRef.current.delete(key);
    setCurrentNotification(undefined);
  }, []);

  // Memoize the context value to prevent unnecessary re-renders
  const contextValue = React.useMemo(() => ({ show, close }), [show, close]);

  // Get custom styling for neutral severity
  const getNeutralAlertSx = () => {
    const isDark = theme.palette.mode === 'dark';
    return {
      backgroundColor: isDark
        ? theme.palette.grey[700]
        : theme.palette.grey[100],
      color: isDark ? theme.palette.grey[100] : theme.palette.grey[800],
      '& .MuiAlert-icon': {
        color: isDark ? theme.palette.grey[300] : theme.palette.grey[600],
      },
      '& .MuiAlert-action': {
        color: isDark ? theme.palette.grey[300] : theme.palette.grey[600],
      },
    };
  };

  const severity = currentNotification?.options.severity ?? 'info';
  const persistent = PERSISTENT_SEVERITIES.has(severity);

  return (
    <NotificationContext.Provider value={contextValue}>
      {children}
      {currentNotification && (
        <Snackbar
          key={currentNotification.key}
          open={open}
          autoHideDuration={
            persistent
              ? null
              : currentNotification.options.autoHideDuration ||
                DEFAULT_AUTO_HIDE_MS
          }
          onClose={handleClose}
          anchorOrigin={anchorOrigin}
          TransitionProps={{ onExited: handleExited }}
        >
          <Alert
            onClose={handleClose}
            severity={
              currentNotification.options.severity === 'neutral'
                ? 'info'
                : currentNotification.options.severity || 'info'
            }
            variant="filled"
            sx={{
              width: '100%',
              ...(currentNotification.options.severity === 'neutral'
                ? getNeutralAlertSx()
                : {}),
            }}
            elevation={6}
            // Announced through the live announcer; a role here would read it twice.
            role="none"
          >
            {currentNotification.message}
          </Alert>
        </Snackbar>
      )}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  const context = React.useContext(NotificationContext);
  if (context === undefined) {
    throw new Error(
      'useNotifications must be used within a NotificationProvider'
    );
  }
  return context;
}
