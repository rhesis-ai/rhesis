'use server';

import { signIn } from '@/auth';
import { redirect } from 'next/navigation';

export async function handleSignIn(provider?: string, options?: any) {
  if (!provider) return;
  return signIn(provider, options);
}

export async function handleSignOut() {
  console.log('🔵 [DEBUG] Server handleSignOut called - redirecting to /auth/signout');
  // Redirect to our client-side signout page which will handle the actual logout
  redirect('/auth/signout');
} 