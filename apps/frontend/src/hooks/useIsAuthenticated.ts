'use client';

import { useSession } from 'next-auth/react';

/** Mirrors NextAuth's own `useSession().status` literal union. */
export type SessionStatus = 'authenticated' | 'loading' | 'unauthenticated';

/**
 * Whether NextAuth has resolved a valid session. The single check nearly
 * every client-side auth gate in this app boils down to — named here so call
 * sites read as intent instead of repeating the `status === 'authenticated'`
 * string literal.
 *
 * Accepts `undefined` because some components receive status as an optional
 * prop threaded down from a parent's `useSession()` rather than calling it
 * directly; treat "not yet known" the same as "not authenticated".
 */
export function isAuthenticated(status: SessionStatus | undefined): boolean {
  return status === 'authenticated';
}

/** Whether NextAuth is still resolving the session on first load. */
export function isSessionLoading(status: SessionStatus | undefined): boolean {
  return status === 'loading';
}

/** Whether NextAuth has resolved the session and found no signed-in user. */
export function isSessionUnauthenticated(
  status: SessionStatus | undefined
): boolean {
  return status === 'unauthenticated';
}

/**
 * Convenience hook for call sites that only need the authenticated/not
 * boolean and don't otherwise need `session.data` or the raw `status`.
 */
export function useIsAuthenticated(): boolean {
  const { status } = useSession();
  return isAuthenticated(status);
}
