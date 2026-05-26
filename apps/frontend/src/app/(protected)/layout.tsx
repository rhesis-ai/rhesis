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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60_000,
      gcTime: 30 * 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

interface ExtendedUser {
  id: string;
  name?: string | null;
  email?: string | null;
  image?: string | null;
  organization_id?: string | null;
}

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session } = useSession();
  const pathname = usePathname();
  const user = session?.user as ExtendedUser | undefined;
  const isOnboarding = pathname?.startsWith('/onboarding');
  const hasOrganization = !!user?.organization_id && !isOnboarding;

  const content = hasOrganization ? (
    <AppShell sidebar={<Sidebar />}>{children}</AppShell>
  ) : (
    // During onboarding (or when org is missing) render without nav chrome
    <>{children}</>
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthErrorBoundary>
        <FeaturesProvider>
          <WebSocketProvider>
            {!isOnboarding && <VerificationBanner />}
            {content}
          </WebSocketProvider>
        </FeaturesProvider>
      </AuthErrorBoundary>
    </QueryClientProvider>
  );
}
