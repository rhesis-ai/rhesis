import { CommentsClient } from '../comments-client';

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

describe('CommentsClient', () => {
  let client: CommentsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new CommentsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches comments for an entity', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'c1' }]));
    const result = await client.getComments('test', 'entity-id-1');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/comments/entity/test/entity-id-1`),
      expect.any(Object)
    );
    expect(result).toHaveLength(1);
  });

  it('paginates getComments until response is smaller than limit', async () => {
    const page1 = Array.from({ length: 100 }, (_, i) => ({ id: `c${i}` }));
    const page2 = [{ id: 'c100' }];
    fetchMock
      .mockResolvedValueOnce(makeFetch(page1))
      .mockResolvedValueOnce(makeFetch(page2));

    const result = await client.getComments('test', 'entity-id-1');

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toContain('skip=0');
    expect(fetchMock.mock.calls[1][0]).toContain('skip=100');
    expect(result).toHaveLength(101);
  });

  it('creates a comment with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-c' }));
    const payload = { content: 'Hello', entity_type: 'test', entity_id: 'e1' };
    await client.createComment(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/comments');
    expect(opts.method).toBe('POST');
  });

  it('updates a comment with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'c1' }));
    await client.updateComment('c1', { content: 'Updated' } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/comments/c1');
    expect(opts.method).toBe('PUT');
  });

  it('deletes a comment with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'c1' }));
    await client.deleteComment('c1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/comments/c1');
    expect(opts.method).toBe('DELETE');
  });

  it('adds an emoji reaction with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'c1' }));
    await client.addEmojiReaction('c1', '👍');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/comments/c1/emoji/');
    expect(opts.method).toBe('POST');
  });
});
