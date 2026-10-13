/**
 * Streaming destinations API client.
 *
 * URL surface: `ee/backend/src/rhesis/backend/ee/audit/streaming/router.py`.
 * Every call is gated on `FeatureName.AUDIT_LOG` (404 without it) and
 * `audit_log:manage`. The list carries each destination's health.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import type {
  AuditDestination,
  AuditDestinationCreate,
  AuditDestinationCreated,
  TestEventResult,
} from '../destinations';

export const AUDIT_DESTINATIONS_PATH = '/audit-destinations';

function destinationPath(id: string): string {
  return `${AUDIT_DESTINATIONS_PATH}/${encodeURIComponent(id)}`;
}

export class AuditDestinationsClient extends BaseApiClient {
  async listDestinations(): Promise<AuditDestination[]> {
    return this.fetch<AuditDestination[]>(`${AUDIT_DESTINATIONS_PATH}/`, {
      cache: 'no-store',
    });
  }

  /** A webhook's `signing_secret` comes back here and nowhere else. */
  async createDestination(
    body: AuditDestinationCreate
  ): Promise<AuditDestinationCreated> {
    return this.fetch<AuditDestinationCreated>(`${AUDIT_DESTINATIONS_PATH}/`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /** Resuming resets the failure count and continues from the cursor. */
  async setPaused(id: string, paused: boolean): Promise<AuditDestination> {
    return this.fetch<AuditDestination>(destinationPath(id), {
      method: 'PATCH',
      body: JSON.stringify({ paused }),
    });
  }

  async deleteDestination(id: string): Promise<void> {
    return this.fetch<void>(destinationPath(id), { method: 'DELETE' });
  }

  /** A failed delivery is a 200 with `delivered: false`, not a thrown error. */
  async sendTestEvent(id: string): Promise<TestEventResult> {
    return this.fetch<TestEventResult>(`${destinationPath(id)}/test`, {
      method: 'POST',
    });
  }
}
