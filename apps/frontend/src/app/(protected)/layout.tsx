'use client';

import * as React from 'react';
import AuthErrorBoundary from './error-boundary';
import { useSession } from 'next-auth/react';
import { usePathname } from 'next/navigation';
import VerificationBanner from '@/components/auth/VerificationBanner';
import AppLayout from '@/components/layout/AppLayout';
import { useNavigation } from '@/components/navigation/NavigationContext';

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
  const { navigation } = useNavigation();
  const user = session?.user as ExtendedUser | undefined;
  const isOnboarding = pathname?.startsWith('/onboarding');
  const hasOrganization = !!user?.organization_id && !isOnboarding;

  return (
    <AuthErrorBoundary>
      {!isOnboarding && <VerificationBanner />}
      {hasOrganization ? (
        <AppLayout navigation={navigation}>{children}</AppLayout>
      ) : (
        <>{children}</>
      )}
    </AuthErrorBoundary>
  );
}
