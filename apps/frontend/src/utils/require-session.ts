import { auth } from '@/auth';
import type { Session } from 'next-auth';

/**
 * Server-component guard: throws when there's no valid session, so the
 * nearest `error.tsx` renders the generic error boundary. Centralizes the
 * `if (!session || session.error) throw ...` check every page repeated with
 * a slightly different message, even though `error.tsx` displays them all
 * the same way.
 */
export async function requireSession(): Promise<Session> {
  const session = await auth();
  if (!session || session.error) {
    throw new Error('Authentication required');
  }
  return session;
}
