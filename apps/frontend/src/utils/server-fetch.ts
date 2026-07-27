import { getServerBackendUrl } from './url-resolver';

/**
 * Minimal server-side fetch wrapper for backend API calls from Server
 * Components. Resolves the backend URL, sets `cache: 'no-store'`, and
 * optionally injects an Authorization header.
 *
 * Returns the raw `Response` — callers handle JSON parsing and error mapping
 * themselves (keeps this layer thin and composable).
 */
export function serverFetch(
  path: string,
  options?: { accessToken?: string }
): Promise<Response> {
  const url = new URL(path, getServerBackendUrl());
  const headers: Record<string, string> = {};
  if (options?.accessToken) {
    headers['Authorization'] = `Bearer ${options.accessToken}`;
  }
  return fetch(url, { headers, cache: 'no-store' });
}
