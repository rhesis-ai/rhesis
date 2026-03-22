import { PromptsClient } from '../prompts-client';

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

describe('PromptsClient', () => {
  let client: PromptsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new PromptsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches prompts with no options (no extra query params)', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'p1' }]));
    const result = await client.getPrompts();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/prompts`),
      expect.any(Object)
    );
    expect(result).toHaveLength(1);
  });

  it('includes skip and limit when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getPrompts({ skip: 10, limit: 20 });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('skip=10');
    expect(calledUrl).toContain('limit=20');
  });

  it('includes topic_id, behavior_id, and category_id when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getPrompts({
      topic_id: 't1',
      behavior_id: 'b1',
      category_id: 'c1',
    });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('topic_id=t1');
    expect(calledUrl).toContain('behavior_id=b1');
    expect(calledUrl).toContain('category_id=c1');
  });

  it('fetches a single prompt by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'p1' }));
    await client.getPrompt('p1');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/prompts/p1'),
      expect.any(Object)
    );
  });

  it('creates a prompt with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-p' }));
    const payload = { content: 'Test prompt' };
    await client.createPrompt(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/prompts');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject(payload);
  });

  it('deletes a prompt with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'p1' }));
    await client.deletePrompt('p1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/prompts/p1');
    expect(opts.method).toBe('DELETE');
  });
});
