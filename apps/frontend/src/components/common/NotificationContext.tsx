import * as React from 'react';
import { Snackbar, Alert } from '@mui/material';

export type NotificationSeverity = 'success' | 'info' | 'warning' | 'error';

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

const NotificationContext = React.createContext<NotificationContextType | undefined>(undefined);

let notificationCount = 0;

export function NotificationProvider({ 
  children,
  anchorOrigin = { vertical: 'bottom', horizontal: 'right' }
}: { 
  children: React.ReactNode;
  anchorOrigin?: { vertical: 'top' | 'bottom'; horizontal: 'left' | 'right' };
}) {
  const [notifications, setNotifications] = React.useState<NotificationItem[]>([]);
  const [open, setOpen] = React.useState(false);
  const [currentNotification, setCurrentNotification] = React.useState<NotificationItem | undefined>(
    undefined,
  );

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

  const show = (message: string, options: NotificationOptions = {}) => {
    const key = options.key || `notification-${++notificationCount}`;
    
    // Check for duplicate if key is provided
    if (options.key && notifications.some(n => n.key === options.key)) {
      return key;
    }

    setNotifications(prev => [...prev, { message, options, key }]);
    return key;
  };

  const close = (key: string) => {
    if (currentNotification?.key === key) {
      setOpen(false);
    } else {
      setNotifications(prev => prev.filter(notification => notification.key !== key));
    }
  };

  const handleClose = (_event?: any, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpen(false);
  };

  const handleExited = () => {
    setCurrentNotification(undefined);
  };

  return (
    <NotificationContext.Provider value={{ show, close }}>
      {children}
      {currentNotification && (
        <Snackbar
          key={currentNotification.key}
          open={open}
          autoHideDuration={currentNotification.options.autoHideDuration || 6000}
          onClose={handleClose}
          anchorOrigin={anchorOrigin}
          TransitionProps={{ onExited: handleExited }}
        >
          <Alert
            onClose={handleClose}
            severity={currentNotification.options.severity || 'info'}
            variant="filled"
            sx={{ width: '100%' }}
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
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
} 