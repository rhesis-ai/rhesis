'use server';

import { AuthError } from 'next-auth';
import type { AuthProvider } from '@toolpad/core';
import { redirect } from 'next/navigation';

export interface SignInResult {
  error?: string;
  type?: string;
}

export async function handleProviderSignIn(
  provider: AuthProvider,
  formData: FormData,
  callbackUrl?: string
): Promise<SignInResult | void> {
  try {
    // Redirect to home page for unified login experience
    // The callbackUrl can be passed as a URL parameter if needed
    const redirectUrl = callbackUrl ? `/?return_to=${encodeURIComponent(callbackUrl)}` : '/';
    redirect(redirectUrl);
  } catch (error) {
    if (error instanceof Error && error.message === 'NEXT_REDIRECT') {
      throw error;
    }
    
    if (error instanceof AuthError) {
      return {
        error: 'An error with Auth.js occurred.',
        type: error.type,
      };
    }
    
    return {
      error: 'Something went wrong.',
      type: 'UnknownError',
    };
  }
} 