import { TestResultsClient } from '../test-results-client';

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
});
