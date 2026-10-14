'use client';

import * as React from 'react';
import { Box, useTheme } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';
import NextTopLoader from 'nextjs-toploader';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionProvider } from 'next-auth/react';
import { NavigationProvider } from '../navigation/NavigationProvider';
import { NotificationProvider } from '../common/NotificationContext';
import { OnboardingProvider } from '@/contexts/OnboardingContext';
import { type LayoutProps } from '../../types/navigation';
import { ActiveProjectProvider } from '@/contexts/ActiveProjectContext';
import { OrganizationProvider } from '@/contexts/OrganizationContext';
import { CurrencyProvider } from '@/contexts/CurrencyContext';
import { QuickStartProvider } from '@/contexts/QuickStartContext';
import { useSessionGuard } from '@/hooks/useSessionGuard';
import { userSettingsKeys } from '@/constants/query-keys';
import { scaledVh } from '@/styles/viewport-scaling';
// Side-effect import: pulls ee_bootstrap into the *client* bundle so
// EE feature registrations land in the client-side registry as well as
// the server-side one. Layout.tsx imports the same module for the
// server bundle. Both imports are idempotent.
import '@/ee_bootstrap';
import '@/lib/org-settings-tabs-bootstrap';

function SessionGuard({ children }: { children: React.ReactNode }) {
  useSessionGuard();
  return <>{children}</>;
}

export function LayoutContent({
  children,
  session,
  navigation,
  branding,
  authentication,
  initialActiveProject = null,
  initialProjects = null,
  initialUserSettings = null,
  initialOrganization = null,
  initialQuickStart = false,
}: Omit<LayoutProps, 'theme'>) {
  const theme = useTheme();
  const [queryClient] = React.useState(() => {
    const qc = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 5 * 60_000,
          gcTime: 30 * 60_000,
          refetchOnWindowFocus: false,
        },
      },
    });
    // Pre-seed the user settings cache so useUserSettings and
    // ActiveProjectProvider's default_project lookup hit the cache instead
    // of issuing a redundant client-side GET /users/settings.
    const userScope = session?.user?.id ?? '';
    if (userScope && initialUserSettings) {
      qc.setQueryData(userSettingsKeys.all(userScope), initialUserSettings);
    }
    return qc;
  });
  // Build sx prop conditionally
  const boxSx = React.useMemo(() => {
    const baseStyles = {
      display: 'flex',
      flexDirection: 'column',
      minHeight: scaledVh(),
    };

    if (initialQuickStart) {
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
  }, [initialQuickStart]);

  return (
    <SessionProvider session={session} refetchOnWindowFocus={false}>
      <SessionGuard>
        <AppRouterCacheProvider options={{ enableCssLayer: true }}>
          <CssBaseline />
          <NextTopLoader
            color={theme.palette.primary.main}
            showSpinner={false}
            shadow={false}
          />
          <QueryClientProvider client={queryClient}>
            <QuickStartProvider value={initialQuickStart}>
              <ActiveProjectProvider
                initialActiveProject={initialActiveProject}
                initialProjects={initialProjects}
              >
                <OrganizationProvider initialOrganization={initialOrganization}>
                  {/* Inside OrganizationProvider and the query client: it reads
                      the organization's default currency and the user's
                      override from both. */}
                  <CurrencyProvider>
                    <NotificationProvider>
                      <OnboardingProvider>
                        {/* Root of the laptop zoom ladder — see
                          `styles/viewport-scaling.css`. Everything the app
                          renders itself lives in here so it scales as one
                          piece; MUI's body-level portals deliberately stay
                          outside it so their JS-computed positions are not
                          scaled a second time. */}
                        <div data-ui-scale-root>
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
                        </div>
                      </OnboardingProvider>
                    </NotificationProvider>
                  </CurrencyProvider>
                </OrganizationProvider>
              </ActiveProjectProvider>
            </QuickStartProvider>
          </QueryClientProvider>
        </AppRouterCacheProvider>
      </SessionGuard>
    </SessionProvider>
  );
}
