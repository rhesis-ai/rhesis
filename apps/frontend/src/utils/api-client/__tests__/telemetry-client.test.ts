import { TelemetryClient } from '../telemetry-client';

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

describe('TelemetryClient', () => {
  let client: TelemetryClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TelemetryClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('lists traces with query params at /telemetry/traces', async () => {
    fetchMock.mockResolvedValue(makeFetch({ traces: [], total: 0 }));
    await client.listTraces({ project_id: 'proj-1', offset: 0, limit: 10 });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain(`${BASE_URL}/telemetry/traces`);
    expect(calledUrl).toContain('project_id=proj-1');
    expect(calledUrl).toContain('offset=0');
    expect(calledUrl).toContain('limit=10');
  });

  it('omits undefined and empty-string params from listTraces URL', async () => {
    fetchMock.mockResolvedValue(makeFetch({ traces: [], total: 0 }));
    await client.listTraces({ project_id: 'proj-1', environment: '' });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).not.toContain('environment');
    expect(calledUrl).not.toContain('undefined');
  });

  it('gets a trace detail with traceId and projectId', async () => {
    fetchMock.mockResolvedValue(makeFetch({ trace_id: 'trace-1', spans: [] }));
    await client.getTrace('trace-1', 'proj-1');
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/telemetry/traces/trace-1');
    expect(calledUrl).toContain('project_id=proj-1');
  });

  it('gets metrics with project_id at /telemetry/metrics', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ total_traces: 10, average_latency: 100 })
    );
    await client.getMetrics({ project_id: 'proj-1' });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/telemetry/metrics');
    expect(calledUrl).toContain('project_id=proj-1');
  });

  it('includes environment in metrics URL when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch({ total_traces: 5 }));
    await client.getMetrics({
      project_id: 'proj-2',
      environment: 'production',
    });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('environment=production');
  });
});
