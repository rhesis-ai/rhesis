'use client';

import { clearAllSessionData } from './session';
import { signOut } from 'next-auth/react';

// Add a flag to prevent multiple simultaneous logout attempts
let isLoggingOut = false;

export async function handleClientSignOut() {
  // Prevent multiple simultaneous logout attempts
  if (isLoggingOut) {
    return;
  }

  isLoggingOut = true;

  try {
    // Clear all session data first (cookies, localStorage, etc.)
    await clearAllSessionData();

    // Then call NextAuth signOut with redirect to ensure complete cleanup
    await signOut({
      redirect: true,
      callbackUrl: '/?session_expired=true&force_logout=true',
    });
  } catch (error) {
    // Ultimate fallback: force redirect with session expired flags
    window.location.href = '/?session_expired=true&force_logout=true';
  } finally {
    // Reset the flag
    isLoggingOut = false;
  }
}
