import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import type {
  PlatformSyncRequest,
  PlatformSyncResource,
  PlatformSyncSummary,
} from './interfaces/platform-sync';

/**
 * Client for the local-only `/platform-sync` endpoints. The backend refuses
 * these routes (404) on production/cloud deployments, so this is only usable in
 * a local dev environment.
 */
export class PlatformSyncClient extends BaseApiClient {
  /** List the resource types that can be synced (drives the checkbox UI). */
  async getResources(): Promise<PlatformSyncResource[]> {
    return this.fetch<PlatformSyncResource[]>(
      `${API_ENDPOINTS.platformSync}/resources`,
      { cache: 'no-store' }
    );
  }

  /** Pull the selected resources from the platform into the local database. */
  async sync(payload: PlatformSyncRequest): Promise<PlatformSyncSummary> {
    return this.fetch<PlatformSyncSummary>(API_ENDPOINTS.platformSync, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}
