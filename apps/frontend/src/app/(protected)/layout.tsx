'use client';

import * as React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AuthErrorBoundary from './error-boundary';
import { useSession } from 'next-auth/react';
import { usePathname } from 'next/navigation';
import VerificationBanner from '@/components/auth/VerificationBanner';
import { FeaturesProvider } from '@/contexts/FeaturesContext';
import { AppShell } from '@/components/layout/AppShell';
import { Sidebar } from '@/components/navigation/Sidebar';
import { WebSocketProvider } from '@/contexts/WebSocketContext';

interface ExtendedUser {
  id: string;
  name?: string | null;
  email?: string | null;
  image?: string | null;
  organization_id?: string | null;
}

/**
 * Routes that render as standalone full-screen views without the app
 * navigation chrome (sidebar). The test-run comparison view opens in its own
 * tab and, per design, should not show the sidebar/navbar.
 */
const CHROMELESS_ROUTE_PATTERNS = [/^\/test-runs\/[^/]+\/compare\/?$/];

function isChromelessRoute(pathname: string | null): boolean {
  if (!pathname) return false;
  return CHROMELESS_ROUTE_PATTERNS.some(pattern => pattern.test(pathname));
}

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60_000,
            gcTime: 30 * 60_000,
            refetchOnWindowFocus: false,
          },
        },
      })
  );
  const { data: session } = useSession();
  const pathname = usePathname();
  const user = session?.user as ExtendedUser | undefined;
  const isOnboarding =
    pathname === '/onboarding' ||
    (pathname?.startsWith('/onboarding/') ?? false);
  const chromeless = isChromelessRoute(pathname);
  const hasOrganization = !!user?.organization_id && !isOnboarding;

  const content =
    hasOrganization && !chromeless ? (
      <AppShell sidebar={<Sidebar />}>{children}</AppShell>
    ) : (
      // During onboarding, when org is missing, or for chromeless routes
      // (e.g. the comparison tab) render without nav chrome
      <>{children}</>
    );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthErrorBoundary>
        <FeaturesProvider>
          <WebSocketProvider>
            {!isOnboarding && !chromeless && <VerificationBanner />}
            {content}
          </WebSocketProvider>
        </FeaturesProvider>
      </AuthErrorBoundary>
    </QueryClientProvider>
  );
}
