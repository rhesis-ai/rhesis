import { TestsClient } from '../tests-client';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';

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
    text: () => Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
  } as unknown as Response);
}

describe('TestsClient', () => {
  let client: TestsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TestsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('getTests', () => {
    it('fetches tests with default pagination', async () => {
      const mockTests = [
        { id: 'test-1', priority: 1, prompt_id: 'prompt-1', created_at: '2024-01-01', updated_at: '2024-01-01' },
        { id: 'test-2', priority: 0, prompt_id: 'prompt-2', created_at: '2024-01-01', updated_at: '2024-01-01' },
      ];
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockTests, 200, { 'x-total-count': '2' }) as unknown as Response
      );

      const result = await client.getTests();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/tests'),
        expect.objectContaining({ credentials: 'include' })
      );
      expect(result.data).toHaveLength(2);
      expect(result.pagination.totalCount).toBe(2);
    });

    it('converts numeric priority 1 to Medium', async () => {
      const mockTests = [
        { id: 'test-1', priority: 1, prompt_id: 'p1', created_at: '2024-01-01', updated_at: '2024-01-01' },
      ];
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockTests, 200, { 'x-total-count': '1' }) as unknown as Response
      );

      const result = await client.getTests();

      expect(result.data[0].priorityLevel).toBe('Medium');
    });

    it('converts numeric priority 0 to Low', async () => {
      const mockTests = [
        { id: 'test-1', priority: 0, prompt_id: 'p1', created_at: '2024-01-01', updated_at: '2024-01-01' },
      ];
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockTests, 200, { 'x-total-count': '1' }) as unknown as Response
      );

      const result = await client.getTests();

      expect(result.data[0].priorityLevel).toBe('Low');
    });

    it('converts numeric priority 2 to High', async () => {
      const mockTests = [
        { id: 'test-1', priority: 2, prompt_id: 'p1', created_at: '2024-01-01', updated_at: '2024-01-01' },
      ];
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockTests, 200, { 'x-total-count': '1' }) as unknown as Response
      );

      const result = await client.getTests();

      expect(result.data[0].priorityLevel).toBe('High');
    });

    it('converts numeric priority 3 to Urgent', async () => {
      const mockTests = [
        { id: 'test-1', priority: 3, prompt_id: 'p1', created_at: '2024-01-01', updated_at: '2024-01-01' },
      ];
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockTests, 200, { 'x-total-count': '1' }) as unknown as Response
      );

      const result = await client.getTests();

      expect(result.data[0].priorityLevel).toBe('Urgent');
    });

    it('includes filter in request when provided', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' }) as unknown as Response
      );

      await client.getTests({ filter: "behavior eq 'safety'" });

      // $filter is URL-encoded as %24filter in query strings
      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('%24filter');
      expect(calledUrl).toContain('safety');
    });

    it('sends Authorization header with session token', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' }) as unknown as Response
      );

      await client.getTests();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });

    it('returns pagination metadata with correct page numbers', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '100' }) as unknown as Response
      );

      const result = await client.getTests({ skip: 0, limit: 50 });

      expect(result.pagination.totalCount).toBe(100);
      expect(result.pagination.totalPages).toBe(2);
      expect(result.pagination.currentPage).toBe(0);
    });

    it('handles missing x-total-count header gracefully', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([]) as unknown as Response
      );

      const result = await client.getTests();

      expect(result.pagination.totalCount).toBe(0);
    });
  });

  describe('getTest', () => {
    it('fetches a single test by id', async () => {
      const mockTest = {
        id: 'test-abc',
        priority: 2,
        prompt_id: 'p1',
        created_at: '2024-01-01',
        updated_at: '2024-01-01',
      };
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockTest) as unknown as Response
      );

      const result = await client.getTest('test-abc');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/tests/test-abc'),
        expect.anything()
      );
      expect(result.id).toBe('test-abc');
      expect(result.priorityLevel).toBe('High');
    });
  });

  describe('createTest', () => {
    it('sends POST request with test data', async () => {
      const newTest = {
        prompt_id: 'prompt-xyz' as unknown as `${string}-${string}-${string}-${string}-${string}`,
        priority: 1,
      };
      const createdTest = { id: 'new-test', ...newTest };
      fetchMock.mockResolvedValue(
        makeFetchResponse(createdTest) as unknown as Response
      );

      await client.createTest(newTest);

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/tests'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"prompt_id":"prompt-xyz"'),
        })
      );
    });
  });

  describe('updateTest', () => {
    it('sends PUT request with test update data', async () => {
      const updateData = { priority: 2 };
      const updatedTest = { id: 'test-1', priority: 2, prompt_id: 'p1', created_at: '2024-01-01', updated_at: '2024-01-01' };
      fetchMock.mockResolvedValue(
        makeFetchResponse(updatedTest) as unknown as Response
      );

      await client.updateTest('test-1', updateData);

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/tests/test-1'),
        expect.objectContaining({
          method: 'PUT',
          body: expect.stringContaining('"priority":2'),
        })
      );
    });
  });

  describe('deleteTest', () => {
    it('sends DELETE request for the test', async () => {
      const deletedTest = { id: 'test-1', prompt_id: 'p1', created_at: '2024-01-01', updated_at: '2024-01-01' };
      fetchMock.mockResolvedValue(
        makeFetchResponse(deletedTest) as unknown as Response
      );

      await client.deleteTest('test-1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/tests/test-1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('error handling', () => {
    it('throws an error with status on 404', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404) as unknown as Response
      );

      await expect(client.getTest('missing-id')).rejects.toThrow('API error: 404');
    });

    it('throws an error with status on 500', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Server error' }, 500) as unknown as Response
      );

      await expect(client.getTest('test-1')).rejects.toThrow('API error: 500');
    });

    it('throws network error as descriptive message', async () => {
      fetchMock.mockRejectedValue(
        new TypeError('Failed to fetch')
      );

      await expect(client.getTest('test-1')).rejects.toThrow(
        expect.objectContaining({ message: expect.stringContaining('Network error') })
      );
    });
  });

  describe('getTestStats', () => {
    it('fetches test stats without parameters', async () => {
      const mockStats = {
        total: 100,
        stats: {},
        metadata: { generated_at: '2024-01-01', organization_id: 'org-1', entity_type: 'test' },
      };
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockStats) as unknown as Response
      );

      const result = await client.getTestStats();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(`${BASE_URL}/tests/stats`),
        expect.anything()
      );
      expect(result.total).toBe(100);
    });

    it('includes query parameters when provided', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ total: 10, stats: {}, metadata: {} }) as unknown as Response
      );

      await client.getTestStats({ top: 5, months: 3 });

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('top=5'),
        expect.anything()
      );
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('months=3'),
        expect.anything()
      );
    });
  });
});
