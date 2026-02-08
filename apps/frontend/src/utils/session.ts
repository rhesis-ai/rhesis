'use client';

import { API_CONFIG } from './api-client/config';

export interface User {
  id: string;
  name: string;
  email: string;
  image?: string;
  organization_id?: string;
}

export interface Session {
  user: User;
}

export async function getSession(): Promise<Session | null> {
  // Get session token from cookie
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('next-auth.session-token='))
    ?.split('=')[1];

  if (!cookieValue) return null;

  // Extract the actual JWT token from the session data
  let token = cookieValue;
  try {
    const sessionData = JSON.parse(decodeURIComponent(cookieValue));
    if (
      sessionData &&
      typeof sessionData === 'object' &&
      sessionData.session_token
    ) {
      token = sessionData.session_token;
    }
  } catch (_error) {
    // If JSON parsing fails, treat as direct token
  }

  try {
    const response = await fetch(
      `${API_CONFIG.baseUrl}/auth/verify?session_token=${token}`,
      {
        headers: {
          Accept: 'application/json',
        },
      }
    );

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    if (!data.authenticated || !data.user) {
      return null;
    }

    return {
      user: data.user,
    };
  } catch (_error) {
    return null;
  }
}

export async function clearAllSessionData() {
  // Step 1: Call backend logout endpoint to clear server-side session
  // Try to get the session token first to pass to backend
  let sessionToken: string | undefined;
  try {
    // Extract session token from cookie directly
    const cookieValue = document.cookie
      .split('; ')
      .find(row => row.startsWith('next-auth.session-token='))
      ?.split('=')[1];

    if (cookieValue) {
      // Try to parse as JSON first
      try {
        const sessionData = JSON.parse(decodeURIComponent(cookieValue));
        if (
          sessionData &&
          typeof sessionData === 'object' &&
          sessionData.session_token
        ) {
          sessionToken = sessionData.session_token;
        }
      } catch {
        // If JSON parsing fails, treat as direct token
        sessionToken = decodeURIComponent(cookieValue);
      }
    }
  } catch (_error) {}

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

  // Step 2: Clear ALL frontend cookies
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

  // Step 3: Clear ALL local storage items
  localStorage.clear();

  // Step 4: Clear ALL session storage items
  sessionStorage.clear();

  // Note: Redirect will be handled by the calling function (NextAuth signOut)
}
