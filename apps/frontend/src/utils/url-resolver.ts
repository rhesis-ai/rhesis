/**
 * URL resolution utilities for handling cross-platform localhost issues
 *
 * This module provides centralized URL resolution to fix macOS IPv6 localhost
 * resolution issues where macOS resolves 'localhost' to IPv6 (::1) first,
 * while the backend typically only listens on IPv4 (127.0.0.1).
 */

/**
 * Resolves localhost URLs to use IPv4 (127.0.0.1) instead of hostname 'localhost'
 * This prevents IPv6 resolution issues on macOS while maintaining compatibility
 * with other platforms.
 *
 * @param url - The URL to resolve
 * @returns URL with localhost replaced by 127.0.0.1
 */
export function resolveLocalhostUrl(url: string): string {
  return url.replace(/localhost/g, '127.0.0.1');
}

/**
 * Gets the API base URL for the browser's direct calls to the backend's
 * unauthenticated `/auth/*` endpoints, from the runtime config the root layout
 * injects into `window.__ENV__` (or `API_BASE_URL` when called on the server).
 *
 * Throws when it is not configured. There used to be a `http://localhost:8080`
 * fallback here, which only ever looked right in local dev: in a deployed
 * environment it pointed the sign-in, verify-email, magic-link and
 * reset-password flows at the visitor's own machine instead of failing.
 *
 * @returns Resolved API base URL
 */
export function getClientApiBaseUrl(): string {
  const baseUrl =
    typeof window === 'undefined'
      ? process.env.API_BASE_URL
      : window.__ENV__?.apiBaseUrl;
  if (!baseUrl) {
    throw new Error(
      'API_BASE_URL is not configured — cannot resolve the backend URL for ' +
        'authentication requests. Set API_BASE_URL for the frontend, ' +
        'wherever its environment comes from (Helm `config.apiBaseUrl`, ' +
        'docker-compose, or the dev scripts).'
    );
  }
  return resolveLocalhostUrl(baseUrl);
}

/**
 * Gets the backend URL for server-side requests with localhost resolution
 * Uses BACKEND_URL environment variable or falls back to default
 *
 * @returns Resolved backend URL
 */
export function getServerBackendUrl(): string {
  const baseUrl = process.env.BACKEND_URL || 'http://backend:8080';
  return resolveLocalhostUrl(baseUrl);
}

/**
 * Gets the appropriate base URL based on execution environment
 * - Client-side: same-origin `/api/backend` BFF proxy. The browser never
 *   holds a backend access token; the proxy injects `Authorization`
 *   server-side from the httpOnly session cookie (see `src/auth.ts`'s
 *   `getFreshAccessToken()` and `src/app/api/backend/[...path]/route.ts`).
 * - Server-side: Uses BACKEND_URL for container-to-container communication,
 *   calling the backend directly (no self-proxy hop).
 *
 * @returns Resolved base URL appropriate for the current environment
 */
export function getBaseUrl(): string {
  if (typeof window === 'undefined') {
    // Server-side: use BACKEND_URL for container-to-container communication
    return getServerBackendUrl();
  } else {
    // Client-side: same-origin BFF proxy, not the backend directly.
    // `joinUrl` strips leading slashes from every part it's given and never
    // re-adds one, so a bare `/api/backend` path would resolve relative to
    // the current page path instead of the origin root — must be absolute.
    return `${window.location.origin}/api/backend`;
  }
}

export function shouldUseSecureCookies(): boolean {
  return (process.env.FRONTEND_URL || '').startsWith('https://');
}
