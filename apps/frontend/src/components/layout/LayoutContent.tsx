'use client';

import * as React from 'react';
import { Box, useTheme } from '@mui/material';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { SessionProvider } from 'next-auth/react';
import { usePathname } from 'next/navigation';
import { NavigationProvider } from '../navigation/NavigationProvider';
import { NotificationProvider } from '../common/NotificationContext';
import { type NavigationItem, type LayoutProps } from '../../types/navigation';

function getAllSegments(items: NavigationItem[]): string[] {
  return items.reduce<string[]>((acc, item) => {
    if (item.kind === 'page') {
      acc.push(item.segment);
      if (item.children) {
        acc.push(...getAllSegments(item.children));
      }
    }
    return acc;
  }, []);
}

export function LayoutContent({
  children,
  session,
  navigation,
  branding,
  authentication,
}: Omit<LayoutProps, 'theme'>) {
  const theme = useTheme();
  const pathname = usePathname();
  const protectedSegments = React.useMemo(
    () => getAllSegments(navigation),
    [navigation]
  );

  const isProtectedRoute = React.useMemo(() => {
    if (!pathname) return false;
    // Remove leading slash for comparison
    const currentPath = pathname.startsWith('/') ? pathname.slice(1) : pathname;
    return protectedSegments.some(
      segment =>
        currentPath === segment || currentPath.startsWith(`${segment}/`)
    );
  }, [pathname, protectedSegments]);

  // Use state to avoid hydration mismatch - start with false (matches server)
  const [isQuickStartMode, setIsQuickStartMode] = React.useState(false);

  // Check Quick Start mode after mount (client-side only)
  React.useEffect(() => {
    const { isQuickStartEnabled } = require('@/utils/quick_start');
    setIsQuickStartMode(isQuickStartEnabled());
  }, []);

  // Build sx prop conditionally
  const boxSx = React.useMemo(() => {
    const baseStyles = {
      display: 'flex',
      flexDirection: 'column',
      minHeight: '100vh',
    };

    if (isQuickStartMode) {
      return {
        ...baseStyles,
        // Hide the account menu button when Quick Start mode is enabled
        '& [aria-label="Account"]': {
          display: 'none !important',
        },
        '& button[aria-label*="account" i]': {
          display: 'none !important',
        },
        // Target the account preview/popover button
        '& .ToolpadAccountButton, & [class*="AccountButton"]': {
          display: 'none !important',
        },
        // Target any button in the toolbar that has an avatar (account button)
        '& header button:has(.MuiAvatar-root)': {
          display: 'none !important',
        },
        '& .MuiToolbar-root button:has(.MuiAvatar-root)': {
          display: 'none !important',
        },
      };
    }

    return baseStyles;
  }, [isQuickStartMode]);

  return (
    <SessionProvider session={session} refetchOnWindowFocus={false}>
      <AppRouterCacheProvider options={{ enableCssLayer: true }}>
        <NotificationProvider>
          <Box sx={boxSx}>
            <Box sx={{ flex: 1 }}>
              <NavigationProvider
                navigation={navigation}
                branding={branding}
                session={session}
                authentication={authentication}
                theme={theme}
              >
                {children}
              </NavigationProvider>
            </Box>
          </Box>
        </NotificationProvider>
      </AppRouterCacheProvider>
    </SessionProvider>
  );
}
