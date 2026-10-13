/**
 * Pins the audit log client's URL contract against
 * `ee/backend/src/rhesis/backend/ee/audit/router.py`.
 */

import { BaseApiClient } from '@/utils/api-client/base-client';
import { AuditLogClient } from '../audit-log-client';

type ClientProto = {
  fetch: (...args: unknown[]) => Promise<unknown>;
  fetchPaginated: (...args: unknown[]) => Promise<unknown>;
};

describe('AuditLogClient', () => {
  let fetchSpy: jest.SpyInstance<Promise<unknown>, unknown[]>;
  let pageSpy: jest.SpyInstance<Promise<unknown>, unknown[]>;

  beforeEach(() => {
    const proto = BaseApiClient.prototype as unknown as ClientProto;
    fetchSpy = jest.spyOn(proto, 'fetch').mockResolvedValue({});
    pageSpy = jest.spyOn(proto, 'fetchPaginated').mockResolvedValue({});
  });

  afterEach(() => {
    fetchSpy.mockRestore();
    pageSpy.mockRestore();
  });

  it('lists newest first on occurred_at by default', async () => {
    await new AuditLogClient().listEvents();
    expect(pageSpy).toHaveBeenCalledWith(
      '/audit-events',
      {
        skip: 0,
        limit: 25,
        sort_by: 'occurred_at',
        sort_order: 'desc',
        $filter: undefined,
      },
      { cache: 'no-store' }
    );
  });

  it('caps the page at the API limit of 100', async () => {
    await new AuditLogClient().listEvents({ limit: 500, skip: 100 });
    expect(pageSpy).toHaveBeenCalledWith(
      '/audit-events',
      expect.objectContaining({ limit: 100, skip: 100 }),
      expect.anything()
    );
  });

  it('passes the OData filter through', async () => {
    await new AuditLogClient().listEvents({ $filter: "trace_id eq 'abc'" });
    expect(pageSpy).toHaveBeenCalledWith(
      '/audit-events',
      expect.objectContaining({ $filter: "trace_id eq 'abc'" }),
      expect.anything()
    );
  });

  it('reads one event by id', async () => {
    await new AuditLogClient().getEvent('e1');
    expect(fetchSpy).toHaveBeenCalledWith('/audit-events/e1', {
      cache: 'no-store',
    });
  });

  it('reads the action catalog', async () => {
    await new AuditLogClient().listActions();
    expect(fetchSpy).toHaveBeenCalledWith('/audit-events/actions');
  });
});
