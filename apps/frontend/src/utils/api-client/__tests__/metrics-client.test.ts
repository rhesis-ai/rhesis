import { MetricsClient } from '../metrics-client';
import { UUID } from 'crypto';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';
const METRIC_ID = 'm1m1m1m1-0000-0000-0000-000000000001' as UUID;
const BEHAVIOR_ID = 'b1b1b1b1-0000-0000-0000-000000000001' as UUID;

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

describe('MetricsClient', () => {
  let client: MetricsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new MetricsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches paginated metrics with default params', async () => {
    fetchMock.mockResolvedValue(
      makeFetch([{ id: 'm1' }], 200, { 'x-total-count': '1' })
    );
    const result = await client.getMetrics();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/metrics`),
      expect.any(Object)
    );
    expect(result.data).toHaveLength(1);
    expect(result.pagination.totalCount).toBe(1);
  });

  it('getAllMetrics paginates through multiple pages', async () => {
    const page1 = Array.from({ length: 100 }, (_, i) => ({ id: `m${i}` }));
    const page2 = Array.from({ length: 50 }, (_, i) => ({ id: `m${100 + i}` }));
    fetchMock
      .mockResolvedValueOnce(makeFetch(page1, 200, { 'x-total-count': '150' }))
      .mockResolvedValueOnce(makeFetch(page2, 200, { 'x-total-count': '150' }));

    const result = await client.getAllMetrics();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result).toHaveLength(150);
  });

  it('fetches a single metric by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: METRIC_ID }));
    await client.getMetric(METRIC_ID);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/metrics/${METRIC_ID}`),
      expect.any(Object)
    );
  });

  it('creates a metric with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-m' }));
    const payload = { name: 'New Metric' };
    await client.createMetric(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/metrics');
    expect(opts.method).toBe('POST');
  });

  it('adds behavior to metric with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch(null, 204));
    await client.addBehaviorToMetric(METRIC_ID, BEHAVIOR_ID);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/metrics/${METRIC_ID}/behaviors/${BEHAVIOR_ID}`);
    expect(opts.method).toBe('POST');
  });

  it('removes behavior from metric with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch(null, 204));
    await client.removeBehaviorFromMetric(METRIC_ID, BEHAVIOR_ID);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/metrics/${METRIC_ID}/behaviors/${BEHAVIOR_ID}`);
    expect(opts.method).toBe('DELETE');
  });
});
