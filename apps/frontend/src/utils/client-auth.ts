'use client';

import { clearAllSessionData } from './session';
import { signOut } from 'next-auth/react';

// Add a flag to prevent multiple simultaneous logout attempts
let isLoggingOut = false;

export async function handleClientSignOut() {
  console.log(
    '[ERROR] [DEBUG] handleClientSignOut called - starting logout process'
  );

  // Prevent multiple simultaneous logout attempts
  if (isLoggingOut) {
    console.log(
      '[ERROR] [DEBUG] Logout already in progress, skipping duplicate request'
    );
    return;
  }

  isLoggingOut = true;

  try {
    // Clear all session data first (cookies, localStorage, etc.)
    console.log('[ERROR] [DEBUG] About to call clearAllSessionData()');
    await clearAllSessionData();
    console.log('[ERROR] [DEBUG] clearAllSessionData() completed successfully');

    // Then call NextAuth signOut with redirect to ensure complete cleanup
    console.log('[ERROR] [DEBUG] About to call NextAuth signOut with redirect');
    await signOut({
      redirect: true,
      callbackUrl: '/?session_expired=true&force_logout=true',
    });
  } catch (error) {
    console.error('[ERROR] [DEBUG] Error during sign out:', error);

    // Ultimate fallback: force redirect with session expired flags
    console.log('[ERROR] [DEBUG] Ultimate fallback redirect');
    window.location.href = '/?session_expired=true&force_logout=true';
  } finally {
    // Reset the flag
    isLoggingOut = false;
  }
}
