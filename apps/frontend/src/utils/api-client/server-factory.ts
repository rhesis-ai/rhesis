import { headers } from 'next/headers';
import { ApiClientFactory } from './client-factory';
import { getServerActiveProjectId } from '../server-active-project';
import { getFreshAccessToken } from '@/auth';

/**
 * Build an ApiClientFactory for server-side use (Server Components, server
 * actions, route handlers).
 *
 * This is the ONLY sanctioned way to construct an ApiClientFactory on the
 * server. It resolves a fresh access token via `getFreshAccessToken()`
 * (refreshing if the cookie's token is stale — a plain `session.session_token`
 * read cannot do this, and the session object no longer exposes the token at
 * all) and reads the active project from the `rh_active_project_id` cookie
 * (which `document.cookie` cannot see during SSR), threading both through so
 * every request carries `Authorization` and `X-Project-Id`. Building the
 * factory directly on the server would omit the project header and leak
 * cross-project data.
 *
 * Client components must NOT use this — they construct `ApiClientFactory`
 * directly (no token) and calls route through the `/api/backend` proxy.
 *
 * Ignores `refreshedCookie`: Server Component renders can't set cookies (only
 * a Route Handler or Server Action can), so a refresh performed here can't be
 * persisted — the next `/api/backend` proxy call (or navigation) catches the
 * cookie up. See `getFreshAccessToken()`'s docstring.
 */
export async function createServerApiFactory(): Promise<ApiClientFactory> {
  const [{ accessToken }, projectId] = await Promise.all([
    getFreshAccessToken({ headers: await headers() }),
    getServerActiveProjectId(),
  ]);
  return new ApiClientFactory(accessToken ?? undefined, projectId);
}
