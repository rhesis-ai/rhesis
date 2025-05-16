'use server';

import { signIn, signOut } from '@/auth';

export async function handleSignIn(provider?: string, options?: any) {
  if (!provider) return;
  return signIn(provider, options);
}

export async function handleSignOut(options?: any) {
  return signOut(options);
} 