import { ServicesClient } from '../services-client';
import type { TestPipelineRequest } from '../interfaces/test-set';

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

/** A streaming response whose body yields the given NDJSON lines then closes. */
function makeNdjsonStream(lines: string[]) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      lines.forEach(line => controller.enqueue(encoder.encode(`${line}\n`)));
      controller.close();
    },
  });
  return Promise.resolve({
    ok: true,
    status: 200,
    body,
  } as unknown as Response);
}

/** A streaming response whose body never yields anything and never closes --
 * simulates a stalled connection (e.g. the underlying model call hangs). */
function makeStalledStream() {
  const body = new ReadableStream<Uint8Array>({ start() {} });
  return Promise.resolve({
    ok: true,
    status: 200,
    body,
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

  describe('generateTestPipelineStream', () => {
    const request: TestPipelineRequest = { prompt: 'Test the login flow' };

    it('parses each NDJSON line as an event', async () => {
      fetchMock.mockResolvedValue(
        makeNdjsonStream([
          '{"type":"config_done","total":1}',
          '{"type":"done"}',
        ])
      );
      const onEvent = jest.fn();

      await client.generateTestPipelineStream(request, { onEvent });

      expect(onEvent).toHaveBeenCalledWith({ type: 'config_done', total: 1 });
      expect(onEvent).toHaveBeenCalledWith({ type: 'done' });
    });

    it('rejects instead of hanging forever when the stream stalls', async () => {
      jest.useFakeTimers();
      fetchMock.mockResolvedValue(makeStalledStream());
      const onEvent = jest.fn();

      const result = client.generateTestPipelineStream(request, { onEvent });
      const assertion = expect(result).rejects.toThrow(/Stream stalled/);
      await jest.advanceTimersByTimeAsync(150_000);
      await assertion;

      expect(onEvent).not.toHaveBeenCalled();
      jest.useRealTimers();
    });
  });
});
