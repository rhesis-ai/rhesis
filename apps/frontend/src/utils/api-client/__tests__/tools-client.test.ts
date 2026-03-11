import { ToolsClient } from '../tools-client';

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

describe('ToolsClient', () => {
  let client: ToolsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new ToolsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches paginated tools with default params', async () => {
    fetchMock.mockResolvedValue(
      makeFetch([{ id: 'tool-1' }], 200, { 'x-total-count': '1' })
    );
    const result = await client.getTools();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/tools`),
      expect.any(Object)
    );
    expect(result.data).toHaveLength(1);
    expect(result.pagination.totalCount).toBe(1);
  });

  it('fetches a single tool by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'tool-1' }));
    await client.getTool('tool-1');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/tools/tool-1'),
      expect.any(Object)
    );
  });

  it('creates a tool with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-tool' }));
    const payload = { name: 'Jira' };
    await client.createTool(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tools');
    expect(opts.method).toBe('POST');
  });

  it('updates a tool with PATCH', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'tool-1' }));
    await client.updateTool('tool-1', { name: 'Updated Tool' } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tools/tool-1');
    expect(opts.method).toBe('PATCH');
  });

  it('deletes a tool with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch(null, 204));
    await client.deleteTool('tool-1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tools/tool-1');
    expect(opts.method).toBe('DELETE');
  });
});
