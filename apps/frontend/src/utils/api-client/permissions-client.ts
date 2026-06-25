import { BaseApiClient } from './base-client';

/**
 * Client for the `/me/permissions` endpoint.
 *
 * `getMyPermissions` returns the caller's effective capabilities for a given
 * project (or org-scoped when `projectId` is omitted). The full catalog
 * (`GET /capabilities`) is consumed only by the EE role editor and will be
 * added with it (see rbac_frontend_authoring_ui.plan.md).
 */
export class PermissionsClient extends BaseApiClient {
  async getMyPermissions(projectId?: string): Promise<string[]> {
    const query = projectId ? `?project_id=${projectId}` : '';
    return this.fetch<string[]>(`/me/permissions${query}`, {
      cache: 'no-store',
    });
  }
}
