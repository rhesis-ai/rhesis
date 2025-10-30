'use server';

import { redirect } from 'next/navigation';
import { signOut } from '@/auth';

export async function handleSignIn() {
  redirect('/');
}

export async function handleSignOut() {
  try {
    // Call NextAuth signOut first to clear server-side session
    await signOut({
      redirectTo: '/auth/signout', // Redirect to our client logout page
      redirect: false, // We'll handle the redirect manually
    });
  } catch (error) {
    // Continue with redirect even if server signOut fails
  }

  // Redirect to our client-side signout page which will handle the actual logout
  redirect('/auth/signout');
}
