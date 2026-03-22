import { TypeLookupClient } from '../type-lookup-client';

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

describe('TypeLookupClient', () => {
  let client: TypeLookupClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TypeLookupClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches type lookups with default sort params', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'tl-1' }]));
    const result = await client.getTypeLookups();
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain(`${BASE_URL}/type_lookups`);
    expect(calledUrl).toContain('sort_by=created_at');
    expect(calledUrl).toContain('sort_order=desc');
    expect(result).toHaveLength(1);
  });

  it('includes skip, limit, and $filter when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getTypeLookups({
      skip: 5,
      limit: 25,
      $filter: "type eq 'metric'",
    });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('skip=5');
    expect(calledUrl).toContain('limit=25');
    expect(calledUrl).toContain('%24filter');
  });

  it('fetches a single type lookup by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'tl-1' }));
    await client.getTypeLookup('tl-1');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/type_lookups/tl-1'),
      expect.any(Object)
    );
  });

  it('creates a type lookup with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-tl' }));
    await client.createTypeLookup({
      name: 'metric_type',
      description: 'Metric type',
    } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/type_lookups');
    expect(opts.method).toBe('POST');
  });

  it('updates a type lookup with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'tl-1' }));
    await client.updateTypeLookup('tl-1', { name: 'updated' } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/type_lookups/tl-1');
    expect(opts.method).toBe('PUT');
  });

  it('deletes a type lookup with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'tl-1' }));
    await client.deleteTypeLookup('tl-1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/type_lookups/tl-1');
    expect(opts.method).toBe('DELETE');
  });
});
