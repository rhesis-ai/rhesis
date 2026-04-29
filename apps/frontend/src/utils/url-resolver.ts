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
 * Gets the API base URL for browser requests: relative `/api` so Next.js
 * rewrites can proxy to `BACKEND_URL` without changing the browser origin.
 *
 * @returns Relative API base URL
 */
export function getClientApiBaseUrl(): string {
  return '/api';
}

/**
 * Same-origin base for FastAPI `/auth/*` (and similar) from the browser.
 * Must not use `/api/auth/*` — that path is reserved for NextAuth.
 * Proxied by `next.config.mjs` via `/api/upstream/:path*` → `BACKEND_URL/:path*`.
 */
export function getClientUpstreamApiBaseUrl(): string {
  return '/api/upstream';
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
 * - Client-side: Same-origin `/api` (proxied to backend by Next.js)
 * - Server-side: Uses BACKEND_URL for container-to-container communication
 *
 * @returns Resolved base URL appropriate for the current environment
 */
export function getBaseUrl(): string {
  if (typeof window === 'undefined') {
    // Server-side: use BACKEND_URL for container-to-container communication
    return getServerBackendUrl();
  } else {
    return getClientApiBaseUrl();
  }
}
