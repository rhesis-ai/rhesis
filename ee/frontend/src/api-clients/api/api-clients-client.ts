/**
 * EE API client for the AuthClient (token-exchange) CRUD surface.
 *
 * Mirrors the shape of `SSOClient` -- one class per EE feature, each
 * extending `BaseApiClient`. Keeping API Clients on its own client
 * (rather than methods on `OrganizationsClient` in core) is what
 * keeps `AuthClient` and `AuthClientCreated` types out of core's
 * dependency graph.
 *
 * URL surface (see `ee/backend/src/rhesis/backend/ee/api_clients/router.py`):
 *
 *   POST   /orgs/{orgId}/auth-clients               (create + one-shot secret)
 *   GET    /orgs/{orgId}/auth-clients               (list)
 *   GET    /orgs/{orgId}/auth-clients/{id}          (detail)
 *   POST   /orgs/{orgId}/auth-clients/{id}/rotate   (rotate + new one-shot secret)
 *   POST   /orgs/{orgId}/auth-clients/{id}/disable
 *   POST   /orgs/{orgId}/auth-clients/{id}/enable
 *   DELETE /orgs/{orgId}/auth-clients/{id}          (only when disabled)
 *
 * The path is `/orgs/...` (not `/organizations/...`); the backend
 * router uses the shorter prefix to mirror the audience parameter
 * shape `rhesis:org:<slug>`. We hard-code the prefix here rather
 * than introduce a new entry in core's `API_ENDPOINTS` map -- doing
 * so would require a core-side edit for every EE feature, which is
 * the coupling the registry pattern exists to avoid.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import type {
  AuthClient,
  AuthClientCreated,
  AuthClientCreateRequest,
} from '../types';

/**
 * Base path for the API Clients endpoints. Centralised here so a
 * future move (e.g. nesting under `/organizations/...`) is a one-line
 * change rather than a search-and-replace across components.
 */
function basePath(orgId: string): string {
  return `/orgs/${orgId}/auth-clients`;
}

export class ApiClientsClient extends BaseApiClient {
  constructor(sessionToken: string) {
    super(sessionToken);
  }

  /** List clients for the organization. Sorted server-side by `created_at` desc. */
  async listClients(orgId: string): Promise<AuthClient[]> {
    return this.fetch<AuthClient[]>(basePath(orgId));
  }

  /**
   * Create a client. The returned object includes the plaintext
   * `client_secret` -- this is the only call site that produces it.
   * Hand it to the integration owner via a secure channel; we do not
   * keep a copy.
   */
  async createClient(
    orgId: string,
    body: AuthClientCreateRequest
  ): Promise<AuthClientCreated> {
    return this.fetch<AuthClientCreated>(basePath(orgId), {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /** Get a single client (no secret material). */
  async getClient(orgId: string, clientPk: string): Promise<AuthClient> {
    return this.fetch<AuthClient>(`${basePath(orgId)}/${clientPk}`);
  }

  /**
   * Rotate the client's secret and bump `token_epoch`. The new
   * plaintext `client_secret` comes back in the response and the
   * previous one stops working immediately. Issued JWTs minted
   * before the rotation are invalidated on their next refresh by
   * the `iat >= epoch` check.
   */
  async rotateClient(
    orgId: string,
    clientPk: string
  ): Promise<AuthClientCreated> {
    return this.fetch<AuthClientCreated>(
      `${basePath(orgId)}/${clientPk}/rotate`,
      { method: 'POST' }
    );
  }

  /** Soft-disable. New token-exchange requests fail with `invalid_client`. */
  async disableClient(orgId: string, clientPk: string): Promise<AuthClient> {
    return this.fetch<AuthClient>(`${basePath(orgId)}/${clientPk}/disable`, {
      method: 'POST',
    });
  }

  /** Re-enable a previously disabled client. */
  async enableClient(orgId: string, clientPk: string): Promise<AuthClient> {
    return this.fetch<AuthClient>(`${basePath(orgId)}/${clientPk}/enable`, {
      method: 'POST',
    });
  }

  /**
   * Delete a client. The backend enforces that the client must be
   * disabled first; calling this on an enabled client returns a
   * 409. The two-step requirement is deliberate -- a misclick that
   * deletes a live client breaks every integration that depends on it.
   */
  async deleteClient(orgId: string, clientPk: string): Promise<void> {
    return this.fetch<void>(`${basePath(orgId)}/${clientPk}`, {
      method: 'DELETE',
    });
  }
}
