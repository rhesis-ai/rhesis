'use server';

import { AuthError } from 'next-auth';
import { redirect } from 'next/navigation';

/** Minimal auth provider descriptor — replaces @toolpad/core AuthProvider */
interface AuthProvider {
  id: string;
  name: string;
}

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
    const redirectUrl = callbackUrl
      ? `/?return_to=${encodeURIComponent(callbackUrl)}`
      : '/';
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
