import { TestRunsClient } from '../test-runs-client';

function makeFetchResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {}
) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: (key: string) => headers[key.toLowerCase()] ?? null,
      entries: () => Object.entries(headers),
    },
    json: () => Promise.resolve(body),
    text: () =>
      Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
    blob: () =>
      Promise.resolve(
        new Blob([JSON.stringify(body)], { type: 'application/json' })
      ),
  } as unknown as Response);
}

describe('TestRunsClient', () => {
  let client: TestRunsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TestRunsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('getTestRuns', () => {
    it('fetches test runs with default pagination', async () => {
      const mockRuns = [
        { id: 'run-1', created_at: '2024-01-01', updated_at: '2024-01-01' },
        { id: 'run-2', created_at: '2024-01-02', updated_at: '2024-01-02' },
      ];
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockRuns, 200, { 'x-total-count': '2' })
      );

      const result = await client.getTestRuns();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_runs'),
        expect.objectContaining({ credentials: 'include' })
      );
      expect(result.data).toHaveLength(2);
      expect(result.pagination.totalCount).toBe(2);
    });

    it('sends Authorization header', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      await client.getTestRuns();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });

    it('filters by test_configuration_id when provided', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      await client.getTestRuns({ test_configuration_id: 'config-123' });

      // $filter is URL-encoded as %24filter in query strings
      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('%24filter');
      expect(calledUrl).toContain('config-123');
    });

    it('combines custom filter with test_configuration_id filter', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      await client.getTestRuns({
        test_configuration_id: 'config-123',
        filter: "status eq 'active'",
      });

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('config-123');
      expect(calledUrl).toContain('status');
    });

    it('respects custom pagination parameters', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      await client.getTestRuns({ skip: 10, limit: 25 });

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('skip=10');
      expect(calledUrl).toContain('limit=25');
    });
  });

  describe('getTestRun', () => {
    it('fetches a single test run by id', async () => {
      const mockRun = {
        id: 'run-abc',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
      };
      fetchMock.mockResolvedValue(makeFetchResponse(mockRun));

      const result = await client.getTestRun('run-abc');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_runs/run-abc'),
        expect.anything()
      );
      expect(result.id).toBe('run-abc');
    });
  });

  describe('getTestRunsCount', () => {
    it('returns total count from pagination metadata', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '42' })
      );

      const count = await client.getTestRunsCount();

      expect(count).toBe(42);
    });
  });

  describe('createTestRun', () => {
    it('sends POST request with test run data', async () => {
      const newRun = {
        name: 'Test Run 1',
        test_configuration_id:
          'config-1' as unknown as `${string}-${string}-${string}-${string}-${string}`,
      };
      const createdRun = {
        id: 'run-new',
        ...newRun,
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
      };
      fetchMock.mockResolvedValue(makeFetchResponse(createdRun));

      await client.createTestRun(newRun);

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_runs'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"name":"Test Run 1"'),
        })
      );
    });
  });

  describe('updateTestRun', () => {
    it('sends PUT request with update data', async () => {
      const updateData = { name: 'Updated Run' };
      fetchMock.mockResolvedValue(
        makeFetchResponse({ id: 'run-1', ...updateData })
      );

      await client.updateTestRun('run-1', updateData);

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_runs/run-1'),
        expect.objectContaining({
          method: 'PUT',
          body: expect.stringContaining('"name":"Updated Run"'),
        })
      );
    });
  });

  describe('deleteTestRun', () => {
    it('sends DELETE request', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse(null, 204));

      await client.deleteTestRun('run-1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_runs/run-1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('getTestRunsByTestConfiguration', () => {
    it('delegates to getTestRuns with test_configuration_id filter', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      await client.getTestRunsByTestConfiguration('config-456');

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('config-456');
    });
  });

  describe('getTestRunStats', () => {
    it('fetches stats without params', async () => {
      const mockStats = { total: 50, by_status: {} };
      fetchMock.mockResolvedValue(makeFetchResponse(mockStats));

      const result = await client.getTestRunStats();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_runs/stats'),
        expect.anything()
      );
      expect(result).toEqual(mockStats);
    });

    it('appends query params when provided', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse({}));

      await client.getTestRunStats({ test_run_ids: ['run-1', 'run-2'] });

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('test_run_ids=run-1');
      expect(calledUrl).toContain('test_run_ids=run-2');
    });
  });

  describe('error handling', () => {
    it('throws on 404 responses', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404)
      );

      await expect(client.getTestRun('missing-id')).rejects.toThrow(
        'API error: 404'
      );
    });

    it('propagates network errors', async () => {
      fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

      await expect(client.getTestRun('run-1')).rejects.toThrow(
        expect.objectContaining({
          message: expect.stringContaining('Network error'),
        })
      );
    });
  });
});
