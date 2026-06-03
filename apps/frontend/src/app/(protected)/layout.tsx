'use client';

import * as React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AuthErrorBoundary from './error-boundary';
import { useSession } from 'next-auth/react';
import { usePathname } from 'next/navigation';
import VerificationBanner from '@/components/auth/VerificationBanner';
import { FeaturesProvider } from '@/contexts/FeaturesContext';
import { ActiveProjectProvider, useActiveProject } from '@/contexts/ActiveProjectContext';
import { AppShell } from '@/components/layout/AppShell';
import { Sidebar } from '@/components/navigation/Sidebar';
import { WebSocketProvider } from '@/contexts/WebSocketContext';
import NoProjectAccess from '@/components/common/NoProjectAccess';

interface ExtendedUser {
  id: string;
  name?: string | null;
  email?: string | null;
  image?: string | null;
  organization_id?: string | null;
}

/**
 * Inner shell rendered only when the user has an organisation.
 * Must be a child of ActiveProjectProvider so it can call useActiveProject().
 */
function AppContent({
  children,
  isOnboarding,
}: {
  children: React.ReactNode;
  isOnboarding: boolean;
}) {
  const { projects, loading } = useActiveProject();
  const hasNoProjects = !loading && projects.length === 0;

  // Routes that bypass the no-project gate (project creation, onboarding)
  const pathname = usePathname();
  const isProjectCreation = pathname?.startsWith('/projects/create-new') ?? false;

  if (hasNoProjects && !isOnboarding && !isProjectCreation) {
    return (
      <AppShell sidebar={<Sidebar />}>
        <NoProjectAccess />
      </AppShell>
    );
  }

  return <AppShell sidebar={<Sidebar />}>{children}</AppShell>;
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
  const hasOrganization = !!user?.organization_id && !isOnboarding;

  const content = hasOrganization ? (
    <AppContent isOnboarding={isOnboarding}>{children}</AppContent>
  ) : (
    // During onboarding (or when org is missing) render without nav chrome
    <>{children}</>
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthErrorBoundary>
        <FeaturesProvider>
          <ActiveProjectProvider>
            <WebSocketProvider>
              {!isOnboarding && <VerificationBanner />}
              {content}
            </WebSocketProvider>
          </ActiveProjectProvider>
        </FeaturesProvider>
      </AuthErrorBoundary>
    </QueryClientProvider>
  );
}
