import * as React from 'react';
import { Snackbar, Alert, useTheme } from '@mui/material';

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

export function NotificationProvider({
  children,
  anchorOrigin = { vertical: 'bottom', horizontal: 'right' },
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

      // Check for duplicate if key is provided
      if (options.key && notifications.some(n => n.key === options.key)) {
        return key;
      }

      setNotifications(prev => [...prev, { message, options, key }]);
      return key;
    },
    [notifications]
  );

  const close = React.useCallback(
    (key: string) => {
      if (currentNotification?.key === key) {
        setOpen(false);
      } else {
        setNotifications(prev =>
          prev.filter(notification => notification.key !== key)
        );
      }
    },
    [currentNotification]
  );

  const handleClose = (_event?: unknown, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpen(false);
  };

  const handleExited = React.useCallback(() => {
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

  return (
    <NotificationContext.Provider value={contextValue}>
      {children}
      {currentNotification && (
        <Snackbar
          key={currentNotification.key}
          open={open}
          autoHideDuration={
            currentNotification.options.autoHideDuration || 6000
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
