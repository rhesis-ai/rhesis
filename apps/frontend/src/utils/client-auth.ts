'use client';

import { clearAllSessionData } from './session';
import { signOut } from 'next-auth/react';

// Add a flag to prevent multiple simultaneous logout attempts
let isLoggingOut = false;

export async function handleClientSignOut() {
  console.log('🔴 [DEBUG] handleClientSignOut called - starting logout process');
  
  // Prevent multiple simultaneous logout attempts
  if (isLoggingOut) {
    console.log('🔴 [DEBUG] Logout already in progress, skipping duplicate request');
    return;
  }
  
  isLoggingOut = true;
  
  try {
    console.log('🔴 [DEBUG] About to call NextAuth signOut');
    // First, call NextAuth signOut to clear NextAuth session state
    await signOut({ 
      redirect: false, // Don't redirect yet, we'll handle it manually
      callbackUrl: '/' 
    });
    console.log('🔴 [DEBUG] NextAuth signOut completed');
    
    console.log('🔴 [DEBUG] About to call clearAllSessionData()');
    // Then clear all session data which will redirect to login
    await clearAllSessionData();
    console.log('🔴 [DEBUG] clearAllSessionData() completed successfully');
  } catch (error) {
    console.error('🔴 [DEBUG] Error during sign out:', error);
    
    // Fallback: try NextAuth signOut again with redirect
    try {
      console.log('🔴 [DEBUG] Attempting fallback NextAuth signOut with redirect');
      await signOut({ 
        redirect: true,
        callbackUrl: '/' 
      });
    } catch (fallbackError) {
      console.error('🔴 [DEBUG] Fallback NextAuth signOut failed:', fallbackError);
      // Ultimate fallback: force redirect to home page
      console.log('🔴 [DEBUG] Ultimate fallback redirect to /');
      window.location.href = '/';
    }
  } finally {
    // Reset the flag after a delay
    setTimeout(() => {
      isLoggingOut = false;
    }, 2000);
  }
} 