import { BaseApiClient } from './base-client';
import { getApiErrorStatus } from './is-not-found-error';

export type EntityResolution = 'switchable' | 'no_access';

export interface ResolvedEntity {
  resolution: EntityResolution;
  entity_type: string;
  entity_id: string;
  project_id: string | null;
  project_name: string | null;
}

export class ResolveClient extends BaseApiClient {
  async resolveEntity(
    entityType: string,
    entityId: string
  ): Promise<ResolvedEntity | null> {
    try {
      return await this.fetch<ResolvedEntity>(
        `/resolve?entity_type=${encodeURIComponent(entityType)}&entity_id=${encodeURIComponent(entityId)}`
      );
    } catch (error: unknown) {
      if (getApiErrorStatus(error) === 404) {
        return null;
      }
      throw error;
    }
  }
}
