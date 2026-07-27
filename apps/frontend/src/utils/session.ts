'use client';

import { API_CONFIG } from './api-client/config';

export async function clearAllSessionData(sessionToken?: string) {
  // Step 1: Call backend logout endpoint to clear server-side session.
  // The call goes through the same-origin /api/backend proxy, which injects
  // the access token server-side from the httpOnly session cookie — the
  // backend falls back to that Authorization header to revoke refresh
  // tokens when no explicit session_token is passed.

  // Call backend logout with retry logic
  const maxRetries = 2;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const logoutUrl = new URL(`${API_CONFIG.baseUrl}/auth/logout`);
      if (sessionToken) {
        logoutUrl.searchParams.set('session_token', sessionToken);
      }

      const response = await fetch(logoutUrl.toString(), {
        method: 'GET',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
        },
      });

      if (response.ok) {
        break; // Success, exit retry loop
      }

      if (attempt < maxRetries) {
        // Wait before retrying (exponential backoff)
        await new Promise(resolve => setTimeout(resolve, 500 * (attempt + 1)));
      }
    } catch (_error) {
      if (attempt === maxRetries) {
      }
    }
  }

  clearLocalSessionData();
}

/**
 * Clears cookies, localStorage, and sessionStorage without contacting the
 * backend. Use this when there's no session to reliably revoke server-side —
 * e.g. the BFF proxy itself returned 401 because it couldn't resolve/refresh
 * a token from the cookie. Going through `clearAllSessionData()` in that case
 * would route the logout call itself through the same proxy, which mints a
 * *fresh* refresh token via `getFreshAccessToken()` just to immediately
 * revoke it — wasteful, and if repeated (e.g. by a transient/misrouted 401)
 * burns through the refresh-token family for no reason.
 *
 * NOTE: this cannot remove the `next-auth.session-token` cookie — it is
 * httpOnly, invisible to `document.cookie`. Callers must ALSO run NextAuth's
 * `signOut()` so the auth server clears it via Set-Cookie.
 */
export function clearLocalSessionData() {
  // Clear ALL frontend cookies
  // Get all cookies and extract their names
  const allCookies = document.cookie.split(';');
  const cookieNames = allCookies
    .map(cookie => cookie.trim().split('=')[0])
    .filter(name => name.length > 0);

  // Include known authentication cookies in case some aren't in document.cookie yet
  const knownAuthCookies = [
    'next-auth.session-token',
    'next-auth.csrf-token',
    'next-auth.callback-url',
    'next-auth.pkce.code-verifier',
    'next-auth.pkce.state',
    'session',
    'authjs.session-token',
    'authjs.csrf-token',
    'authjs.callback-url',
    '__Host-next-auth.csrf-token',
    '__Secure-next-auth.callback-url',
    '__Secure-next-auth.session-token',
    'next-auth.state',
    'authjs.state',
    'next-auth.nonce',
    'authjs.nonce',
  ];

  // Combine all cookies (remove duplicates)
  const allCookiesToClear = Array.from(
    new Set([...cookieNames, ...knownAuthCookies])
  );

  // Clear each cookie with multiple variations to ensure complete removal
  allCookiesToClear.forEach(name => {
    // Get current hostname
    const hostname = window.location.hostname;
    const domain = hostname.split('.').slice(-2).join('.'); // Get base domain

    // Clear with various path and domain combinations
    const clearStrategies = [
      // Without domain (default)
      `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`,
      `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; SameSite=Lax`,
      `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; SameSite=None; Secure`,

      // With current hostname
      `${name}=; domain=${hostname}; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`,

      // With base domain
      `${name}=; domain=${domain}; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`,

      // With leading dot (broader coverage)
      `${name}=; domain=.${domain}; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`,
    ];

    // For deployed environments, add secure clearing (but no cross-domain clearing)
    if (!hostname.includes('localhost')) {
      clearStrategies.push(
        // Clear with secure flag for HTTPS environments
        `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; Secure`,
        `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; SameSite=Lax; Secure`
      );
    }

    // Apply all clearing strategies
    clearStrategies.forEach(strategy => {
      document.cookie = strategy;
    });
  });

  // Double-check: Try to clear cookies again after a brief moment
  setTimeout(() => {
    allCookiesToClear.forEach(name => {
      document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT`;
    });
  }, 100);

  // Clear ALL local storage items
  localStorage.clear();

  // Clear ALL session storage items
  sessionStorage.clear();

  // Note: Redirect will be handled by the calling function (NextAuth signOut)
}
