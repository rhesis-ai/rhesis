'use server';

import { AuthError } from 'next-auth';
import type { AuthProvider } from '@toolpad/core';
import { handleSignIn } from '../auth';

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
    return await handleSignIn(provider.id, {      
      ...(formData && {
        email: formData.get('email'),
        password: formData.get('password')
      }),      
      redirectTo: callbackUrl ?? '/',
    });
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