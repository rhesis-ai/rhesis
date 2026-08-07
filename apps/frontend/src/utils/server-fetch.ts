import { getServerBackendUrl } from './url-resolver';

type ServerFetchOptions = RequestInit & {
  accessToken?: string;
};

/**
 * Minimal server-side fetch wrapper for backend API calls from Server
 * Components. Resolves the backend URL, defaults `cache` to `'no-store'`,
 * and optionally injects an Authorization header. Remaining `RequestInit`
 * fields (method, body, signal, extra headers, …) are forwarded as-is.
 *
 * Returns the raw `Response` — callers handle JSON parsing and error mapping
 * themselves (keeps this layer thin and composable).
 */
export function serverFetch(
  path: string,
  options: ServerFetchOptions = {}
): Promise<Response> {
  const { accessToken, headers: initHeaders, cache, ...init } = options;
  const headers = new Headers(initHeaders);
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }
  return fetch(new URL(path, getServerBackendUrl()), {
    ...init,
    headers,
    cache: cache ?? 'no-store',
  });
}
