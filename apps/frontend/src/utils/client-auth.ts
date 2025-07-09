'use client';

import { clearAllSessionData } from './session';

export async function handleClientSignOut() {
  console.log('🔴 [DEBUG] handleClientSignOut called - starting logout process');
  
  try {
    console.log('🔴 [DEBUG] About to call clearAllSessionData()');
    // Clear all session data which will redirect to login
    await clearAllSessionData();
    console.log('🔴 [DEBUG] clearAllSessionData() completed successfully');
  } catch (error) {
    console.error('🔴 [DEBUG] Error during sign out:', error);
    // Fallback redirect to home page
    console.log('🔴 [DEBUG] Fallback redirect to /');
    window.location.href = '/';
  }
} 