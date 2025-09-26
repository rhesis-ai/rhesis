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
 * Gets the API base URL for client-side requests with localhost resolution
 * Uses NEXT_PUBLIC_API_BASE_URL environment variable or falls back to default
 *
 * @returns Resolved API base URL
 */
export function getClientApiBaseUrl(): string {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8080';
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
 * - Client-side: Uses NEXT_PUBLIC_API_BASE_URL for browser-to-host communication
 * - Server-side: Uses BACKEND_URL for container-to-container communication
 *
 * @returns Resolved base URL appropriate for the current environment
 */
export function getBaseUrl(): string {
  if (typeof window === 'undefined') {
    // Server-side: use BACKEND_URL for container-to-container communication
    return getServerBackendUrl();
  } else {
    // Client-side: use NEXT_PUBLIC_API_BASE_URL for browser-to-host communication
    return getClientApiBaseUrl();
  }
}
