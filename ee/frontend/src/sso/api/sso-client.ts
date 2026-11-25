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
import type {
  ClaimPath,
  ProviderInfo,
  RoleMapping,
  RoleMappingPreview,
  SeenClaims,
  SSOConfig,
  SSOTestResult,
} from '../types';

export class SSOClient extends BaseApiClient {
  constructor(sessionToken?: string) {
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

  /** Values people signed in with for a claim, and every list claim seen. */
  async getSeenClaims(orgId: string, claim: ClaimPath): Promise<SeenClaims> {
    return this.fetch<SeenClaims>(
      `${API_ENDPOINTS.organizations}/${orgId}/sso/groups`,
      { method: 'POST', body: JSON.stringify({ claim }) }
    );
  }

  /** Who a mapping would change at their next sign-in. */
  async previewRoleMapping(
    orgId: string,
    mapping: RoleMapping
  ): Promise<RoleMappingPreview> {
    return this.fetch<RoleMappingPreview>(
      `${API_ENDPOINTS.organizations}/${orgId}/sso/role-mapping/preview`,
      { method: 'POST', body: JSON.stringify(mapping) }
    );
  }

  /** The identity providers Rhesis knows, in display order. */
  async getProviders(orgId: string): Promise<ProviderInfo[]> {
    return this.fetch<ProviderInfo[]>(
      `${API_ENDPOINTS.organizations}/${orgId}/sso/providers`
    );
  }

  /** Which provider an issuer belongs to (null while it isn't a URL). */
  async detectProvider(
    orgId: string,
    issuerUrl: string
  ): Promise<string | null> {
    const res = await this.fetch<{ provider: string | null }>(
      `${API_ENDPOINTS.organizations}/${orgId}/sso/providers/detect`,
      { method: 'POST', body: JSON.stringify({ issuer_url: issuerUrl }) }
    );
    return res.provider;
  }
}
