'use client';

import { useEffect } from 'react';
import { useSession, signOut } from 'next-auth/react';

export function useSessionGuard() {
  const { data: session } = useSession();

  useEffect(() => {
    if (
      session?.error === 'RefreshTokenError' ||
      session?.error === 'RefreshTokenMissing'
    ) {
      signOut({ callbackUrl: '/?session_expired=true' });
    }
  }, [session?.error]);
}
