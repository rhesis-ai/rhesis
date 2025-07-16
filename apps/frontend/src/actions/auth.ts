'use server';

import { redirect } from 'next/navigation';
import { signOut } from '@/auth';

export async function handleSignIn() {
  redirect('/');
}

export async function handleSignOut() {
  console.log('🔵 [DEBUG] Server handleSignOut called - starting server-side logout');
  
  try {
    // Call NextAuth signOut first to clear server-side session
    console.log('🔵 [DEBUG] Calling NextAuth signOut on server');
    await signOut({ 
      redirectTo: '/auth/signout',  // Redirect to our client logout page
      redirect: false  // We'll handle the redirect manually
    });
    console.log('🔵 [DEBUG] NextAuth signOut completed on server');
  } catch (error) {
    console.error('🔵 [DEBUG] Server NextAuth signOut failed:', error);
    // Continue with redirect even if server signOut fails
  }
  
  console.log('🔵 [DEBUG] Redirecting to /auth/signout for client-side cleanup');
  // Redirect to our client-side signout page which will handle the actual logout
  redirect('/auth/signout');
} 