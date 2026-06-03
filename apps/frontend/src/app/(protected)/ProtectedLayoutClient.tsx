'use client';

import * as React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AuthErrorBoundary from './error-boundary';
import { useSession } from 'next-auth/react';
import { usePathname } from 'next/navigation';
import VerificationBanner from '@/components/auth/VerificationBanner';
import { FeaturesProvider } from '@/contexts/FeaturesContext';
import {
  ActiveProjectProvider,
  useActiveProject,
} from '@/contexts/ActiveProjectContext';
import { AppShell } from '@/components/layout/AppShell';
import { Sidebar } from '@/components/navigation/Sidebar';
import { WebSocketProvider } from '@/contexts/WebSocketContext';
import NoProjectAccess from '@/components/common/NoProjectAccess';
import { type Project } from '@/utils/api-client/interfaces/project';

interface ExtendedUser {
  id: string;
  name?: string | null;
  email?: string | null;
  image?: string | null;
  organization_id?: string | null;
}

const CHROMELESS_ROUTE_PATTERNS = [/^\/test-runs\/[^/]+\/compare\/?$/];

function isChromelessRoute(pathname: string | null): boolean {
  if (!pathname) return false;
  return CHROMELESS_ROUTE_PATTERNS.some(pattern => pattern.test(pathname));
}

function AppContent({
  children,
  isOnboarding,
}: {
  children: React.ReactNode;
  isOnboarding: boolean;
}) {
  const { projects, loading } = useActiveProject();
  const hasNoProjects = !loading && projects.length === 0;

  const pathname = usePathname();
  const isProjectCreation =
    pathname?.startsWith('/projects/create-new') ?? false;

  if (hasNoProjects && !isOnboarding && !isProjectCreation) {
    return (
      <AppShell sidebar={<Sidebar />}>
        <NoProjectAccess />
      </AppShell>
    );
  }

  return <AppShell sidebar={<Sidebar />}>{children}</AppShell>;
}

export default function ProtectedLayoutClient({
  children,
  initialActiveProject,
}: {
  children: React.ReactNode;
  initialActiveProject: Project | null;
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
      <AppContent isOnboarding={isOnboarding}>{children}</AppContent>
    ) : (
      <>{children}</>
    );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthErrorBoundary>
        <FeaturesProvider>
          <ActiveProjectProvider initialActiveProject={initialActiveProject}>
            <WebSocketProvider>
              {!isOnboarding && !chromeless && <VerificationBanner />}
              {content}
            </WebSocketProvider>
          </ActiveProjectProvider>
        </FeaturesProvider>
      </AuthErrorBoundary>
    </QueryClientProvider>
  );
}
