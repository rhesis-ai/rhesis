/**
 * SSO API client.
 *
 * Extracted from `apps/frontend/src/utils/api-client/organizations-client.ts`
 * during the EE separation. The shape mirrors core's `BaseApiClient`
 * subclasses so usage feels identical from EE components -- new up the
 * client with a session token and call methods on it.
 *
 * Why this is its own class rather than methods on `OrganizationsClient`
 * ---------------------------------------------------------------------
 * If the SSO methods stayed on `OrganizationsClient`, the type signatures
 * would have to import `SSOConfig` from `@ee/sso/types` -- which would put
 * `OrganizationsClient` (core) in the dependency graph of EE. By owning
 * its own client class here, EE keeps all SSO-shaped types inside EE; core
 * needs no awareness of `SSOConfig` at all.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import { API_ENDPOINTS } from '@/utils/api-client/config';
import type { SSOConfig, SSOTestResult } from '../types';

export class SSOClient extends BaseApiClient {
  constructor(sessionToken: string) {
    super(sessionToken);
  }

  async getSSOConfig(orgId: string): Promise<SSOConfig | null> {
    try {
      return await this.fetch<SSOConfig>(
        `${API_ENDPOINTS.organizations}/${orgId}/sso`
      );
    } catch {
      return null;
    }
  }

  async updateSSOConfig(orgId: string, config: SSOConfig): Promise<SSOConfig> {
    return this.fetch<SSOConfig>(
      `${API_ENDPOINTS.organizations}/${orgId}/sso`,
      {
        method: 'PUT',
        body: JSON.stringify(config),
      }
    );
  }

  async deleteSSOConfig(orgId: string): Promise<void> {
    return this.fetch(`${API_ENDPOINTS.organizations}/${orgId}/sso`, {
      method: 'DELETE',
    });
  }

  async testSSOConnection(orgId: string): Promise<SSOTestResult> {
    return this.fetch<SSOTestResult>(
      `${API_ENDPOINTS.organizations}/${orgId}/sso/test`,
      {
        method: 'POST',
      }
    );
  }
}
