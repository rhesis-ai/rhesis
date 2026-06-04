import { cookies } from 'next/headers';
import { ACTIVE_PROJECT_COOKIE } from './active-project';

/**
 * Read the active project ID on the server from the `rh_active_project_id` cookie.
 *
 * `document.cookie` is unavailable during SSR, so Server Components must use
 * this helper instead of `readActiveProjectId()`. Pass the returned value as the
 * second argument to `ApiClientFactory` so that server-rendered API calls carry
 * the `X-Project-Id` header and respect project isolation.
 *
 * Returns `undefined` (not `null`) so it can be spread into optional parameters.
 */
export async function getServerActiveProjectId(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(ACTIVE_PROJECT_COOKIE)?.value ?? undefined;
}
