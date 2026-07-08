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

  it('extracts a tool item with POST to /tools/{id}/extract', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ sources: [{ content: 'page body', title: 'Page' }] })
    );
    const result = await client.extractTool('tool-1', {
      url: 'https://notion.so/page',
      include_children: true,
    });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tools/tool-1/extract');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject({
      url: 'https://notion.so/page',
      include_children: true,
    });
    expect(result.sources).toHaveLength(1);
  });

  it('tests tool connection with POST to /tools/test-connection', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ is_authenticated: 'Yes', message: 'Connected' })
    );
    const request = {
      provider_type_id: 'provider-1',
      credentials: { NOTION_TOKEN: 'secret' },
    };
    const result = await client.testToolConnection(request);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tools/test-connection');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject(request);
    expect(result.is_authenticated).toBe('Yes');
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
    expect(url).toContain('/tools/jira/create-ticket-from-task');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject({
      task_id: 'task-id',
      tool_id: 'tool-id',
    });
  });
});
