/**
 * Pins the streaming client's URL contract against
 * `ee/backend/src/rhesis/backend/ee/audit/streaming/router.py`.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import { AuditDestinationsClient } from '../audit-destinations-client';

type ClientProto = {
  fetch: (...args: unknown[]) => Promise<unknown>;
};

describe('AuditDestinationsClient', () => {
  let fetchSpy: jest.SpyInstance<Promise<unknown>, unknown[]>;

  beforeEach(() => {
    const proto = BaseApiClient.prototype as unknown as ClientProto;
    fetchSpy = jest.spyOn(proto, 'fetch').mockResolvedValue({});
  });

  afterEach(() => fetchSpy.mockRestore());

  it('lists uncached', async () => {
    await new AuditDestinationsClient().listDestinations();
    expect(fetchSpy).toHaveBeenCalledWith('/audit-destinations/', {
      cache: 'no-store',
    });
  });

  it('posts the create body as given', async () => {
    const body = {
      kind: 'datadog',
      name: 'DD',
      site: 'datadoghq.eu',
      api_key: 'k',
    } as const;
    await new AuditDestinationsClient().createDestination(body);
    expect(fetchSpy).toHaveBeenCalledWith('/audit-destinations/', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  });

  it('pauses and resumes with PATCH {paused}', async () => {
    const client = new AuditDestinationsClient();
    await client.setPaused('d1', true);
    expect(fetchSpy).toHaveBeenLastCalledWith('/audit-destinations/d1', {
      method: 'PATCH',
      body: '{"paused":true}',
    });
    await client.setPaused('d1', false);
    expect(fetchSpy).toHaveBeenLastCalledWith('/audit-destinations/d1', {
      method: 'PATCH',
      body: '{"paused":false}',
    });
  });

  it('deletes and sends a test event by id', async () => {
    const client = new AuditDestinationsClient();
    await client.deleteDestination('d1');
    expect(fetchSpy).toHaveBeenLastCalledWith('/audit-destinations/d1', {
      method: 'DELETE',
    });
    await client.sendTestEvent('d1');
    expect(fetchSpy).toHaveBeenLastCalledWith('/audit-destinations/d1/test', {
      method: 'POST',
    });
  });
});
