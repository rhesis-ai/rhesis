import { TestResultsClient } from '../test-results-client';

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

describe('TestResultsClient', () => {
  let client: TestResultsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TestResultsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  // -------------------------------------------------------------------------
  // getTestResults
  // -------------------------------------------------------------------------

  it('fetches test results with default pagination', async () => {
    fetchMock.mockResolvedValue(
      makeFetch([{ id: 'r1' }], 200, { 'x-total-count': '1' })
    );

    const result = await client.getTestResults();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/test_results`),
      expect.any(Object)
    );
    expect(result.data).toHaveLength(1);
  });

  it('passes $filter query parameter', async () => {
    fetchMock.mockResolvedValue(makeFetch([], 200, { 'x-total-count': '0' }));

    await client.getTestResults({ filter: "status eq 'passed'" });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('filter');
  });

  // -------------------------------------------------------------------------
  // getTestResultsCount
  // -------------------------------------------------------------------------

  it('getTestResultsCount returns totalCount from pagination', async () => {
    fetchMock.mockResolvedValue(makeFetch([], 200, { 'x-total-count': '42' }));

    const count = await client.getTestResultsCount();
    expect(count).toBe(42);
  });

  // -------------------------------------------------------------------------
  // getTestResult
  // -------------------------------------------------------------------------

  it('fetches a single test result by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'r42' }));

    const result = await client.getTestResult('r42');

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/test_results/r42'),
      expect.any(Object)
    );
    expect(result).toEqual({ id: 'r42' });
  });

  // -------------------------------------------------------------------------
  // createTestResult / updateTestResult / deleteTestResult
  // -------------------------------------------------------------------------

  it('creates a test result with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-r' }));
    const payload = { test_id: 't1', test_run_id: 'tr1' };

    await client.createTestResult(payload as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/test_results');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject(payload);
  });

  it('updates a test result with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'r1' }));

    await client.updateTestResult('r1', { status: 'passed' } as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/test_results/r1');
    expect(opts.method).toBe('PUT');
  });

  it('deletes a test result with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'r1' }));

    await client.deleteTestResult('r1');

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/test_results/r1');
    expect(opts.method).toBe('DELETE');
  });

  // -------------------------------------------------------------------------
  // getTestResultStats
  // -------------------------------------------------------------------------

  it('fetches stats at /test_results/stats', async () => {
    fetchMock.mockResolvedValue(makeFetch({ total: 5 }));

    await client.getTestResultStats();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/test_results/stats'),
      expect.any(Object)
    );
  });

  it('adds top/months/mode query params to stats URL', async () => {
    fetchMock.mockResolvedValue(makeFetch({ total: 5 }));

    await client.getTestResultStats({ top: 5, months: 3, mode: 'test_run' });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('top=5');
    expect(calledUrl).toContain('months=3');
    expect(calledUrl).toContain('mode=test_run');
  });

  // -------------------------------------------------------------------------
  // getComprehensiveTestResultsStats
  // -------------------------------------------------------------------------

  it('builds URL with array filter params', async () => {
    fetchMock.mockResolvedValue(makeFetch({ metadata: {} }));

    await client.getComprehensiveTestResultsStats({
      test_set_ids: ['ts1', 'ts2'],
      behavior_ids: ['b1'],
    });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('test_set_ids=ts1');
    expect(calledUrl).toContain('test_set_ids=ts2');
    expect(calledUrl).toContain('behavior_ids=b1');
  });

  // -------------------------------------------------------------------------
  // createReview
  // -------------------------------------------------------------------------

  it('creates a review for a test result', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'rev1' }));

    await client.createReview('r1', 'status-id', 'Looks good');

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/test_results/r1/reviews');
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.status_id).toBe('status-id');
    expect(body.comments).toBe('Looks good');
  });

  it('uses provided ReviewTarget in createReview', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'rev1' }));

    const target = { type: 'metric' as const, reference: 'm1' };
    await client.createReview('r1', 's1', 'notes', target);

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.target).toEqual(target);
  });

  // -------------------------------------------------------------------------
  // updateReview
  // -------------------------------------------------------------------------

  it('updates a review with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'rev1' }));

    await client.updateReview('r1', 'rev1', { comments: 'Updated' });

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/test_results/r1/reviews/rev1');
    expect(opts.method).toBe('PUT');
  });

  // -------------------------------------------------------------------------
  // deleteReview
  // -------------------------------------------------------------------------

  it('deletes a review with DELETE', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ message: 'deleted', review_id: 'rev1', deleted_review: {} })
    );

    await client.deleteReview('r1', 'rev1');

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/test_results/r1/reviews/rev1');
    expect(opts.method).toBe('DELETE');
  });
});
