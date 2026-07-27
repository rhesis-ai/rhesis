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

/**
 * The `session.user.id`-based cache-scope key used by every context that
 * scopes a react-query cache/`QueryClient` entry by user (`FeaturesContext`,
 * `PermissionsContext`, `OnboardingContext`, `ActiveProjectContext`) — the
 * access token no longer reaches client components (BFF proxy injects it
 * server-side), so it can't double as a scope key here anymore.
 *
 * Falls back to `''` when the id isn't known yet (session still resolving,
 * or unauthenticated). Callers MUST additionally gate on
 * `isAuthenticated(status) && userScope !== ''` — a shared query `enabled`
 * check or effect guard — before using this as a query key or passing it to
 * `fetchQuery`/`setQueryData`. Centralized here so every consumer derives it
 * identically instead of re-deriving `session?.user?.id ?? ''` inline, which
 * previously invited call sites to gate on `isAuthenticated(status)` alone
 * and skip the `userScope` emptiness check.
 */
export function useUserScope(): string {
  const { data: session } = useSession();
  return session?.user?.id ?? '';
}
