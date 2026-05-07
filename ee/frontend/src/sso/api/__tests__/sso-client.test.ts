/**
 * Smoke tests for the EE SSO API client.
 *
 * The 4 SSO methods used to live on `OrganizationsClient` (core); they
 * were extracted into this dedicated EE class during the EE separation
 * so SSO-shaped types stay inside EE. These tests pin the URL shapes
 * and HTTP methods so a future refactor cannot silently break the
 * client/backend contract.
 *
 * `BaseApiClient.fetch` is mocked at the prototype level; the tests
 * don't go over the wire.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import { API_ENDPOINTS } from '@/utils/api-client/config';
import { SSOClient } from '../sso-client';
import type { SSOConfig } from '../../types';

const FAKE_TOKEN = 'test-session-token';
const ORG_ID = '11111111-1111-1111-1111-111111111111';

type FetchableProto = { fetch: (...args: unknown[]) => Promise<unknown> };

describe('SSOClient', () => {
  let fetchSpy: jest.SpyInstance<Promise<unknown>, unknown[]>;

  beforeEach(() => {
    fetchSpy = jest
      .spyOn(BaseApiClient.prototype as unknown as FetchableProto, 'fetch')
      .mockResolvedValue({});
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('getSSOConfig hits GET /organizations/<id>/sso', async () => {
    const client = new SSOClient(FAKE_TOKEN);
    await client.getSSOConfig(ORG_ID);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${API_ENDPOINTS.organizations}/${ORG_ID}/sso`
    );
  });

  it('getSSOConfig returns null when the underlying fetch rejects', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('not found'));
    const client = new SSOClient(FAKE_TOKEN);
    const result = await client.getSSOConfig(ORG_ID);
    expect(result).toBeNull();
  });

  it('updateSSOConfig PUTs the config to /organizations/<id>/sso', async () => {
    const client = new SSOClient(FAKE_TOKEN);
    const config = {
      enabled: true,
      provider_type: 'oidc',
      issuer_url: 'https://example.com',
      client_id: 'client',
      scopes: 'openid email profile',
      auto_provision_users: false,
      allow_insecure_tls: false,
    } as SSOConfig;
    await client.updateSSOConfig(ORG_ID, config);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${API_ENDPOINTS.organizations}/${ORG_ID}/sso`,
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(config),
      })
    );
  });

  it('deleteSSOConfig DELETEs /organizations/<id>/sso', async () => {
    const client = new SSOClient(FAKE_TOKEN);
    await client.deleteSSOConfig(ORG_ID);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${API_ENDPOINTS.organizations}/${ORG_ID}/sso`,
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('testSSOConnection POSTs to /organizations/<id>/sso/test', async () => {
    const client = new SSOClient(FAKE_TOKEN);
    await client.testSSOConnection(ORG_ID);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${API_ENDPOINTS.organizations}/${ORG_ID}/sso/test`,
      expect.objectContaining({ method: 'POST' })
    );
  });
});
