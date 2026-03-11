import { ServicesClient } from '../services-client';

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

describe('ServicesClient', () => {
  let client: ServicesClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new ServicesClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('gets GitHub contents with URL-encoded repo_url param', async () => {
    fetchMock.mockResolvedValue(makeFetch('readme content'));
    await client.getGitHubContents('https://github.com/owner/repo');
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain(`${BASE_URL}/services/github/contents`);
    expect(calledUrl).toContain(
      encodeURIComponent('https://github.com/owner/repo')
    );
  });

  it('posts to /services/openai/json with prompt in body', async () => {
    fetchMock.mockResolvedValue(makeFetch({ result: 'json response' }));
    await client.getOpenAIJson('Summarize this');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/services/openai/json');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject({ prompt: 'Summarize this' });
  });

  it('generates text with POST to /services/generate/text', async () => {
    fetchMock.mockResolvedValue(makeFetch({ text: 'generated text' }));
    await client.generateText('Write a test');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/services/generate/text');
    expect(opts.method).toBe('POST');
  });

  it('searches MCP with POST and query + tool_id in body', async () => {
    fetchMock.mockResolvedValue(
      makeFetch([{ id: 'item-1', url: 'http://a.com', title: 'A' }])
    );
    await client.searchMCP('query', 'tool-1');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/services/mcp/search');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject({
      query: 'query',
      tool_id: 'tool-1',
    });
  });

  it('gets recent activities with limit query param', async () => {
    fetchMock.mockResolvedValue(makeFetch({ activities: [], total_count: 0 }));
    await client.getRecentActivities(25);
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/services/recent-activities');
    expect(calledUrl).toContain('limit=25');
  });

  it('creates a Jira ticket from task with POST', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({
        issue_key: 'PROJ-1',
        issue_url: 'http://jira.com/PROJ-1',
        message: 'Created',
      })
    );
    await client.createJiraTicketFromTask('task-id', 'tool-id');
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/services/mcp/jira/create-ticket-from-task');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject({
      task_id: 'task-id',
      tool_id: 'tool-id',
    });
  });
});
