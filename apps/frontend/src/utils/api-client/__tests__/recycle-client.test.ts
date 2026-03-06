import { RecycleClient } from '../recycle-client';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';

function makeFetch(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {}
) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: (k: string) => headers[k.toLowerCase()] ?? null,
      entries: () => Object.entries(headers),
    },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response);
}

describe('RecycleClient', () => {
  let client: RecycleClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new RecycleClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('restores an item with POST to /recycle/:table/:id/restore', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'item-1' }));
    await client.restoreItem('test_run', 'item-1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`${BASE_URL}/recycle/test_run/item-1/restore`);
    expect(opts.method).toBe('POST');
  });

  it('gets deleted items with default skip and limit', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ model: 'test_run', count: 2, items: [], has_more: false })
    );
    await client.getDeletedItems('test_run');
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/recycle/test_run');
    expect(calledUrl).toContain('skip=0');
    expect(calledUrl).toContain('limit=100');
  });

  it('gets deleted items with custom skip and limit', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ model: 'test', count: 0, items: [], has_more: false })
    );
    await client.getDeletedItems('test', 10, 50);
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('skip=10');
    expect(calledUrl).toContain('limit=50');
  });

  it('gets recycle bin counts at /recycle/stats/counts', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ total_models_with_deleted: 1, counts: {} })
    );
    await client.getRecycleBinCounts();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/recycle/stats/counts'),
      expect.any(Object)
    );
  });

  it('permanently deletes an item with DELETE and confirm=true', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ message: 'Deleted', warning: 'Permanent' })
    );
    await client.permanentlyDeleteItem('test_run', 'item-1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/recycle/test_run/item-1');
    expect(url).toContain('confirm=true');
    expect(opts.method).toBe('DELETE');
  });
});
