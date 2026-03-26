import { AdaptiveTestingClient } from '../adaptive-testing-client';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';
const TEST_SET_ID = 'ts-001';

function makeFetch(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: () => null,
      entries: () => [],
    },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response);
}

describe('AdaptiveTestingClient', () => {
  let client: AdaptiveTestingClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new AdaptiveTestingClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  // -------------------------------------------------------------------------
  // Test Set Operations
  // -------------------------------------------------------------------------

  it('lists adaptive test sets', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'at1' }]));

    await client.getAdaptiveTestSets();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/adaptive_testing`),
      expect.any(Object)
    );
  });

  it('creates an adaptive test set with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-at', name: 'My Set' }));

    await client.createAdaptiveTestSet('My Set', 'Optional desc');

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/adaptive_testing');
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.name).toBe('My Set');
    expect(body.description).toBe('Optional desc');
  });

  it('uses null description when omitted in createAdaptiveTestSet', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'at2' }));

    await client.createAdaptiveTestSet('Set Without Desc');

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.description).toBeNull();
  });

  it('deletes an adaptive test set with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'at-del', name: 'Gone' }));

    await client.deleteAdaptiveTestSet('at-del');

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/adaptive_testing/at-del');
    expect(opts.method).toBe('DELETE');
  });

  it('fetches adaptive settings for a test set', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ default_endpoint: null, metrics: [] })
    );

    await client.getAdaptiveSettings(TEST_SET_ID);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/adaptive_testing/${TEST_SET_ID}/settings`);
    expect(opts.method).toBe('GET');
  });

  it('updates adaptive settings for a test set', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({
        default_endpoint: { id: 'ep1', name: 'Endpoint 1' },
        metrics: [{ id: 'm1', name: 'metric1' }],
      })
    );

    await client.updateAdaptiveSettings(TEST_SET_ID, {
      default_endpoint_id: 'ep1',
      metric_ids: ['m1'],
    });

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/adaptive_testing/${TEST_SET_ID}/settings`);
    expect(opts.method).toBe('PUT');
    const body = JSON.parse(opts.body);
    expect(body.default_endpoint_id).toBe('ep1');
    expect(body.metric_ids).toEqual(['m1']);
  });

  // -------------------------------------------------------------------------
  // Tree
  // -------------------------------------------------------------------------

  it('fetches the full tree for a test set', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'node1', type: 'topic' }]));

    await client.getTree(TEST_SET_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/adaptive_testing/${TEST_SET_ID}/tree`),
      expect.any(Object)
    );
  });

  it('validates the tree structure', async () => {
    fetchMock.mockResolvedValue(makeFetch({ valid: true, errors: [] }));

    await client.validateTree(TEST_SET_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/adaptive_testing/${TEST_SET_ID}/validate`),
      expect.any(Object)
    );
  });

  it('fetches tree statistics', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ total_nodes: 10, total_topics: 3, total_tests: 7 })
    );

    await client.getTreeStats(TEST_SET_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/adaptive_testing/${TEST_SET_ID}/stats`),
      expect.any(Object)
    );
  });

  // -------------------------------------------------------------------------
  // Topic Operations
  // -------------------------------------------------------------------------

  it('fetches topics for a test set', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ path: 'Safety' }]));

    await client.getTopics(TEST_SET_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/adaptive_testing/${TEST_SET_ID}/topics`),
      expect.any(Object)
    );
  });

  it('includes parent query param when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));

    await client.getTopics(TEST_SET_ID, 'Safety');

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('parent=Safety');
  });

  it('creates a topic with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ path: 'Safety' }));
    const topic = { name: 'Safety', description: 'Safety tests' };

    await client.createTopic(TEST_SET_ID, topic as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/adaptive_testing/${TEST_SET_ID}/topics`);
    expect(opts.method).toBe('POST');
  });

  it('updates a topic with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ path: 'Safety2' }));

    await client.updateTopic(TEST_SET_ID, 'Safety', {
      new_name: 'Safety2',
    } as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/adaptive_testing/${TEST_SET_ID}/topics/Safety`);
    expect(opts.method).toBe('PUT');
  });

  it('deletes a topic with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ deleted: true }));

    await client.deleteTopic(TEST_SET_ID, 'Safety');

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe('DELETE');
  });

  // -------------------------------------------------------------------------
  // Test Node Operations
  // -------------------------------------------------------------------------

  it('fetches tests for a test set', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'tn1' }]));

    await client.getTests(TEST_SET_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/adaptive_testing/${TEST_SET_ID}/tests`),
      expect.any(Object)
    );
  });

  it('includes topic filter in getTests URL', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));

    await client.getTests(TEST_SET_ID, 'Safety');

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('topic=Safety');
  });

  it('fetches a single test node by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'tn1' }));

    await client.getTest(TEST_SET_ID, 'tn1');

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/adaptive_testing/${TEST_SET_ID}/tests/tn1`),
      expect.any(Object)
    );
  });

  it('creates a test node with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-tn' }));

    await client.createTest(TEST_SET_ID, { prompt: 'Hello' } as never);

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe('POST');
  });

  it('updates a test node with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'tn1' }));

    await client.updateTest(TEST_SET_ID, 'tn1', { prompt: 'Updated' } as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/tests/tn1');
    expect(opts.method).toBe('PUT');
  });

  it('deletes a test node with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ deleted: true }));

    await client.deleteTest(TEST_SET_ID, 'tn1');

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe('DELETE');
  });

  // -------------------------------------------------------------------------
  // generateOutputs
  // -------------------------------------------------------------------------

  it('sends a POST to /generate_outputs with the request body', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ job_id: 'job-1', status: 'queued' })
    );

    await client.generateOutputs(TEST_SET_ID, {
      endpoint_id: 'ep1',
      test_ids: ['tn1', 'tn2'],
    });

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/adaptive_testing/${TEST_SET_ID}/generate_outputs`);
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.endpoint_id).toBe('ep1');
    expect(body.test_ids).toEqual(['tn1', 'tn2']);
  });
});
