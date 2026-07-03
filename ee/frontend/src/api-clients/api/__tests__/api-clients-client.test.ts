/**
 * URL / HTTP-method pinning for the EE API Clients client.
 *
 * Mirror of `sso-client.test.ts`. Mocks `BaseApiClient.fetch` at the
 * prototype level so the test never goes over the wire; the goal is
 * to make sure the client emits the URLs and methods the backend
 * router expects so a future refactor cannot silently drift.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import { ApiClientsClient } from '../api-clients-client';
import type { AuthClientCreateRequest } from '../../types';

const FAKE_TOKEN = 'test-session-token';
const ORG_ID = '11111111-1111-1111-1111-111111111111';
const CLIENT_PK = '22222222-2222-2222-2222-222222222222';

type FetchableProto = { fetch: (...args: unknown[]) => Promise<unknown> };

describe('ApiClientsClient', () => {
  let fetchSpy: jest.SpyInstance<Promise<unknown>, unknown[]>;

  beforeEach(() => {
    fetchSpy = jest
      .spyOn(BaseApiClient.prototype as unknown as FetchableProto, 'fetch')
      .mockResolvedValue([]);
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it('listClients hits GET /organizations/<id>/auth-clients', async () => {
    const client = new ApiClientsClient(FAKE_TOKEN);
    await client.listClients(ORG_ID);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/organizations/${ORG_ID}/auth-clients`
    );
  });

  it('createClient POSTs the body to /organizations/<id>/auth-clients', async () => {
    fetchSpy.mockResolvedValueOnce({});
    const client = new ApiClientsClient(FAKE_TOKEN);
    const body: AuthClientCreateRequest = {
      client_id: 'brain',
      name: 'br.AI.n',
      expected_subject_azp: 'brain-keycloak',
      expected_subject_audience: 'rhesis-api',
      allowed_scopes: ['full', 'offline_access'],
      default_scope: 'full',
    };
    await client.createClient(ORG_ID, body);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/organizations/${ORG_ID}/auth-clients`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(body),
      })
    );
  });

  it('getClient hits GET /organizations/<id>/auth-clients/<pk>', async () => {
    fetchSpy.mockResolvedValueOnce({});
    const client = new ApiClientsClient(FAKE_TOKEN);
    await client.getClient(ORG_ID, CLIENT_PK);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/organizations/${ORG_ID}/auth-clients/${CLIENT_PK}`
    );
  });

  it('rotateClient POSTs to /organizations/<id>/auth-clients/<pk>/rotate', async () => {
    fetchSpy.mockResolvedValueOnce({});
    const client = new ApiClientsClient(FAKE_TOKEN);
    await client.rotateClient(ORG_ID, CLIENT_PK);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/organizations/${ORG_ID}/auth-clients/${CLIENT_PK}/rotate`,
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('disableClient POSTs to /organizations/<id>/auth-clients/<pk>/disable', async () => {
    fetchSpy.mockResolvedValueOnce({});
    const client = new ApiClientsClient(FAKE_TOKEN);
    await client.disableClient(ORG_ID, CLIENT_PK);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/organizations/${ORG_ID}/auth-clients/${CLIENT_PK}/disable`,
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('enableClient POSTs to /organizations/<id>/auth-clients/<pk>/enable', async () => {
    fetchSpy.mockResolvedValueOnce({});
    const client = new ApiClientsClient(FAKE_TOKEN);
    await client.enableClient(ORG_ID, CLIENT_PK);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/organizations/${ORG_ID}/auth-clients/${CLIENT_PK}/enable`,
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('deleteClient DELETEs /organizations/<id>/auth-clients/<pk>', async () => {
    fetchSpy.mockResolvedValueOnce(undefined);
    const client = new ApiClientsClient(FAKE_TOKEN);
    await client.deleteClient(ORG_ID, CLIENT_PK);
    expect(fetchSpy).toHaveBeenCalledWith(
      `/organizations/${ORG_ID}/auth-clients/${CLIENT_PK}`,
      expect.objectContaining({ method: 'DELETE' })
    );
  });
});
