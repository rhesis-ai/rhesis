import { TagsClient } from '../tags-client';

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

describe('TagsClient', () => {
  let client: TagsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TagsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches tags with no params', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'tag-1' }]));
    const result = await client.getTags();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/tags`),
      expect.any(Object)
    );
    expect(result).toHaveLength(1);
  });

  it('includes skip, limit, sort_by, sort_order when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getTags({
      skip: 5,
      limit: 15,
      sort_by: 'name',
      sort_order: 'asc',
    });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('skip=5');
    expect(calledUrl).toContain('limit=15');
    expect(calledUrl).toContain('sort_by=name');
    expect(calledUrl).toContain('sort_order=asc');
  });

  it('creates a tag with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-tag' }));
    const payload = { name: 'safety' };
    await client.createTag(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tags');
    expect(opts.method).toBe('POST');
  });

  it('assigns a tag to entity with POST to /tags/:entityType/:entityId', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'tag-1' }));
    await client.assignTagToEntity('test' as never, 'entity-1', {
      name: 'safety',
    } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tags/test/entity-1');
    expect(opts.method).toBe('POST');
  });

  it('removes a tag from entity with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ status: 'ok' }));
    await client.removeTagFromEntity('test' as never, 'entity-1', 'tag-1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tags/test/entity-1/tag-1');
    expect(opts.method).toBe('DELETE');
  });

  it('deletes a tag with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'tag-1' }));
    await client.deleteTag('tag-1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tags/tag-1');
    expect(opts.method).toBe('DELETE');
  });
});
