import { StatusClient } from '../status-client';
import { EntityType } from '@/types/entity-type';

const BASE_URL = 'http://localhost/api/backend';

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

describe('StatusClient', () => {
  let client: StatusClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new StatusClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches statuses with default params', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'st-1' }]));
    const result = await client.getStatuses();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/statuses`),
      expect.any(Object)
    );
    expect(result).toHaveLength(1);
  });

  it('includes entity_type when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getStatuses({ entity_type: EntityType.TEST_RUN });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain(`entity_type=${EntityType.TEST_RUN}`);
  });

  it('includes $filter when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getStatuses({ $filter: "name eq 'Active'" });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('%24filter');
  });

  it('includes sort_by and sort_order when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getStatuses({ sort_by: 'name', sort_order: 'asc' });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('sort_by=name');
    expect(calledUrl).toContain('sort_order=asc');
  });

  it('fetches a single status by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'st-1' }));
    await client.getStatus('st-1');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/statuses/st-1'),
      expect.any(Object)
    );
  });
});
