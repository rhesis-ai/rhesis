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

  describe('downloadTestRun', () => {
    it('fetches the download URL for the given test run id', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ data: 'csv' }, 200, {
          'content-type': 'text/csv',
        })
      );

      await client.downloadTestRun('run-dl');

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('/test_runs/run-dl/download');
    });

    it('sends the Authorization header', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse('', 200));

      await client.downloadTestRun('run-dl');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });

    it('does not include credentials: include (unlike regular fetch calls)', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse('', 200));

      await client.downloadTestRun('run-dl');

      const options = fetchMock.mock.calls[0][1] as RequestInit;
      expect(options.credentials).toBeUndefined();
    });

    it('returns a Blob on success', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse({ data: 'csv' }, 200));

      const result = await client.downloadTestRun('run-dl');

      expect(result).toBeInstanceOf(Blob);
    });

    it('throws with "API error: 500" message on server error', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse('Internal Server Error', 500)
      );

      await expect(client.downloadTestRun('run-dl')).rejects.toThrow(
        'API error: 500'
      );
    });
  });

  describe('getTestRunBehaviors', () => {
    it('fetches behaviors for the given test run id', async () => {
      const mockBehaviors = [
        { id: 'beh-1', name: 'Behavior A' },
        { id: 'beh-2', name: 'Behavior B' },
      ];
      fetchMock.mockResolvedValue(makeFetchResponse(mockBehaviors));

      const result = await client.getTestRunBehaviors('run-123');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_runs/run-123/behaviors'),
        expect.anything()
      );
      expect(result).toHaveLength(2);
      expect(result[0]).toMatchObject({ id: 'beh-1', name: 'Behavior A' });
    });

    it('sends credentials and Authorization header', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse([]));

      await client.getTestRunBehaviors('run-123');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          credentials: 'include',
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });

    it('returns an empty array when there are no behaviors', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse([]));

      const result = await client.getTestRunBehaviors('run-empty');

      expect(result).toEqual([]);
    });

    it('throws on non-ok responses', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404)
      );

      await expect(client.getTestRunBehaviors('run-missing')).rejects.toThrow(
        'API error: 404'
      );
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
