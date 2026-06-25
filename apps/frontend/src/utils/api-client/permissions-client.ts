import { BaseApiClient } from './base-client';

/**
 * Client for the `/capabilities` and `/me/permissions` endpoints.
 *
 * `getCapabilities` returns the full catalog of platform capabilities
 * (what *exists*). `getMyPermissions` returns the caller's effective
 * subset for a given project (or org-scoped when `projectId` is omitted).
 */
export class PermissionsClient extends BaseApiClient {
  async getCapabilities(): Promise<string[]> {
    return this.fetch<string[]>('/capabilities', { cache: 'no-store' });
  }

  async getMyPermissions(projectId?: string): Promise<string[]> {
    const query = projectId ? `?project_id=${projectId}` : '';
    return this.fetch<string[]>(`/me/permissions${query}`, {
      cache: 'no-store',
    });
  }
}
