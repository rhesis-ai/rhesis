'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter';
import { SessionProvider } from 'next-auth/react';
import { usePathname } from 'next/navigation';
import { NavigationProvider } from '../navigation/NavigationProvider';
import { NavigationContextProvider } from '../navigation/NavigationContext';
import { NotificationProvider } from '../common/NotificationContext';
import { OnboardingProvider } from '@/contexts/OnboardingContext';
import OnboardingChecklist from '../onboarding/OnboardingChecklist';
import {
  type NavigationItem,
  type BrandingProps,
  type AuthenticationProps,
} from '../../types/navigation';
import { type Session } from 'next-auth';
import { useTheme } from '@mui/material/styles';

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

interface LayoutContentProps {
  children: React.ReactNode;
  session: Session | null;
  navigation: NavigationItem[];
  branding: BrandingProps;
  authentication?: AuthenticationProps;
}

export function LayoutContent({
  children,
  session,
  navigation,
  branding,
  authentication,
}: LayoutContentProps) {
  const theme = useTheme();
  const pathname = usePathname();
  const protectedSegments = React.useMemo(
    () => getAllSegments(navigation),
    [navigation]
  );

  const isProtectedRoute = React.useMemo(() => {
    if (!pathname) return false;
    const currentPath = pathname.startsWith('/') ? pathname.slice(1) : pathname;
    return protectedSegments.some(
      segment =>
        currentPath === segment || currentPath.startsWith(`${segment}/`)
    );
  }, [pathname, protectedSegments]);

  return (
    <SessionProvider session={session} refetchOnWindowFocus={false}>
      <AppRouterCacheProvider options={{ enableCssLayer: true }}>
        <NotificationProvider>
          <OnboardingProvider>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                minHeight: '100vh',
              }}
            >
              <Box sx={{ flex: 1 }}>
                <NavigationContextProvider
                  navigation={navigation}
                  branding={branding}
                >
                  <NavigationProvider
                    navigation={navigation}
                    branding={branding}
                    session={session}
                    authentication={
                      authentication || {
                        signIn: async () => {},
                        signOut: async () => {},
                      }
                    }
                    theme={theme}
                  >
                    {children}
                  </NavigationProvider>
                </NavigationContextProvider>
              </Box>
            </Box>
            {session && isProtectedRoute && <OnboardingChecklist />}
          </OnboardingProvider>
        </NotificationProvider>
      </AppRouterCacheProvider>
    </SessionProvider>
  );
}
