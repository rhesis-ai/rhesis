'use client';

import { clearAllSessionData } from './session';
import { signOut } from 'next-auth/react';

// Add a flag to prevent multiple simultaneous logout attempts
let isLoggingOut = false;

export async function handleClientSignOut(sessionToken?: string) {
  // Prevent multiple simultaneous logout attempts
  if (isLoggingOut) {
    return;
  }

  isLoggingOut = true;

  try {
    // Clear all session data first (cookies, localStorage, etc.). The
    // backend logout request goes through the /api/backend proxy, which
    // injects Authorization from the httpOnly session cookie, so the
    // backend can revoke refresh tokens without a client-held token.
    await clearAllSessionData(sessionToken);

    // Then call NextAuth signOut with redirect to ensure complete cleanup
    await signOut({
      redirect: true,
      callbackUrl: '/?session_expired=true&force_logout=true',
    });
  } catch (_error) {
    // Ultimate fallback: force redirect with session expired flags
    window.location.href = '/?session_expired=true&force_logout=true';
  } finally {
    // Reset the flag
    isLoggingOut = false;
  }
}
