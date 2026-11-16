/**
 * URL resolution utilities for handling cross-platform localhost issues
 *
 * This module provides centralized URL resolution to fix macOS IPv6 localhost
 * resolution issues where macOS resolves 'localhost' to IPv6 (::1) first,
 * while the backend typically only listens on IPv4 (127.0.0.1).
 */

import { publicEnv, serverEnv } from '@/config/runtime-config';

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
 * The public API URL (`API_BASE_URL`) to show API and SDK users, e.g. in a
 * copyable curl example. Display only: the browser never sends requests there,
 * it goes through `getBaseUrl()`. Undefined when not configured.
 */
export function getPublicApiUrl(): string | undefined {
  return publicEnv().apiBaseUrl?.replace(/\/+$/, '') || undefined;
}

/**
 * Gets the backend URL for server-side requests with localhost resolution
 * Uses BACKEND_URL environment variable or falls back to default
 *
 * @returns Resolved backend URL
 */
export function getServerBackendUrl(): string {
  const baseUrl = serverEnv().backendUrl;
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

/**
 * The browser's WebSocket URL: `/ws` on this origin, which the ingress or
 * reverse proxy routes to the backend. `WS_URL` overrides it where nothing
 * routes `/ws` (local dev, docker-compose without a proxy); a path there is
 * resolved against this origin too.
 */
export function getWebSocketUrl(): string {
  const url = new URL(publicEnv().wsUrl ?? '/ws', window.location.href);
  if (url.protocol === 'http:') url.protocol = 'ws:';
  if (url.protocol === 'https:') url.protocol = 'wss:';
  return url.toString();
}

export function shouldUseSecureCookies(): boolean {
  return (serverEnv().frontendUrl ?? '').startsWith('https://');
}
