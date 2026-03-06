import { BehaviorClient } from '../behavior-client';
import { UUID } from 'crypto';

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

const BEHAVIOR_ID = 'b1b1b1b1-0000-0000-0000-000000000001' as UUID;

describe('BehaviorClient', () => {
  let client: BehaviorClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new BehaviorClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  // -------------------------------------------------------------------------
  // getBehaviors
  // -------------------------------------------------------------------------

  it('fetches behaviors with default params', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'b1' }]));

    const result = await client.getBehaviors();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/behaviors`),
      expect.any(Object)
    );
    expect(result).toHaveLength(1);
  });

  it('includes $filter in URL when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));

    await client.getBehaviors({ $filter: "name eq 'Safety'" });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('%24filter');
  });

  // -------------------------------------------------------------------------
  // getBehavior / getBehaviorWithMetrics
  // -------------------------------------------------------------------------

  it('fetches a single behavior by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: BEHAVIOR_ID }));

    await client.getBehavior(BEHAVIOR_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/behaviors/${BEHAVIOR_ID}`),
      expect.any(Object)
    );
  });

  it('fetches a behavior with metrics (includes=metrics in URL)', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: BEHAVIOR_ID, metrics: [] }));

    await client.getBehaviorWithMetrics(BEHAVIOR_ID);

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('include=metrics');
  });

  // -------------------------------------------------------------------------
  // getBehaviorsWithMetrics
  // -------------------------------------------------------------------------

  it('getBehaviorsWithMetrics delegates to getBehaviors', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'b1', metrics: [] }]));

    const result = await client.getBehaviorsWithMetrics();

    expect(result).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // createBehavior / updateBehavior / deleteBehavior
  // -------------------------------------------------------------------------

  it('creates a behavior with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-b' }));
    const payload = { name: 'New Behavior', description: 'desc' };

    await client.createBehavior(payload as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/behaviors');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject(payload);
  });

  it('updates a behavior with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: BEHAVIOR_ID }));

    await client.updateBehavior(BEHAVIOR_ID, { name: 'Updated' } as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/behaviors/${BEHAVIOR_ID}`);
    expect(opts.method).toBe('PUT');
  });

  it('deletes a behavior with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: BEHAVIOR_ID }));

    await client.deleteBehavior(BEHAVIOR_ID);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/behaviors/${BEHAVIOR_ID}`);
    expect(opts.method).toBe('DELETE');
  });

  // -------------------------------------------------------------------------
  // getBehaviorMetrics
  // -------------------------------------------------------------------------

  it('fetches metrics for a behavior', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'm1' }]));

    await client.getBehaviorMetrics(BEHAVIOR_ID);

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain(`/behaviors/${BEHAVIOR_ID}/metrics/`);
    expect(calledUrl).toContain('limit=100');
  });

  it('passes custom skip/limit to getBehaviorMetrics', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));

    await client.getBehaviorMetrics(BEHAVIOR_ID, { skip: 10, limit: 20 });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('skip=10');
    expect(calledUrl).toContain('limit=20');
  });
});
