'use client';

import * as React from 'react';
import AuthErrorBoundary from './error-boundary';
import { useSession } from 'next-auth/react';
import { usePathname } from 'next/navigation';
import VerificationBanner from '@/components/auth/VerificationBanner';
import { FeaturesProvider } from '@/contexts/FeaturesContext';
import { PermissionsProvider } from '@/contexts/PermissionsContext';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
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
 * Routes that render as standalone full-screen views without the app
 * navigation chrome (sidebar). The test-run comparison view opens in its own
 * tab and, per design, should not show the sidebar/navbar.
 */
const CHROMELESS_ROUTE_PATTERNS = [/^\/test-runs\/[^/]+\/compare\/?$/];

function isChromelessRoute(pathname: string | null): boolean {
  if (!pathname) return false;
  return CHROMELESS_ROUTE_PATTERNS.some(pattern => pattern.test(pathname));
}

/**
 * Inner shell rendered only when the user has an organisation and the route
 * is not chromeless. Must be a child of ActiveProjectProvider so it can call
 * useActiveProject().
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

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
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
      // During onboarding, when org is missing, or for chromeless routes
      // (e.g. the comparison tab) render without nav chrome
      <>{children}</>
    );

  return (
    <AuthErrorBoundary>
      <FeaturesProvider>
        <PermissionsProvider>
          <WebSocketProvider>
            {!isOnboarding && !chromeless && <VerificationBanner />}
            {content}
          </WebSocketProvider>
        </PermissionsProvider>
      </FeaturesProvider>
    </AuthErrorBoundary>
  );
}
