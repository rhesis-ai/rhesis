import { ApiClientFactory } from './client-factory';
import { getServerActiveProjectId } from '../server-active-project';

/**
 * Build an ApiClientFactory for server-side use (Server Components, server
 * actions, route handlers).
 *
 * This is the ONLY sanctioned way to construct an ApiClientFactory on the
 * server. It reads the active project from the `rh_active_project_id` cookie
 * (which `document.cookie` cannot see during SSR) and threads it through so
 * every request carries the `X-Project-Id` scope. Building the factory directly
 * on the server would omit the project header and leak cross-project data.
 *
 * Client components must NOT use this — they construct `ApiClientFactory`
 * directly and `BaseApiClient` injects the project from the cookie.
 */
export async function createServerApiFactory(
  sessionToken: string
): Promise<ApiClientFactory> {
  const projectId = await getServerActiveProjectId();
  return new ApiClientFactory(sessionToken, projectId);
}
