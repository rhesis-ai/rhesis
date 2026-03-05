import { TestSetsClient } from '../test-sets-client';

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
    text: () =>
      Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
    blob: () => Promise.resolve(new Blob()),
  } as unknown as Response);
}

const mockTestSet = {
  id: 'ts-1',
  name: 'My Test Set',
  description: 'A test set',
  priority: 1,
  created_at: '2024-01-01',
  updated_at: '2024-01-01',
};

describe('TestSetsClient', () => {
  let client: TestSetsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TestSetsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('getTestSets', () => {
    it('fetches test sets with default pagination', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([mockTestSet], 200, {
          'x-total-count': '1',
        }) as unknown as Response
      );

      const result = await client.getTestSets();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(`${BASE_URL}/test_sets`),
        expect.objectContaining({ credentials: 'include' })
      );
      expect(result.data).toHaveLength(1);
      expect(result.pagination.totalCount).toBe(1);
    });

    it('converts numeric priority 1 to Medium', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([{ ...mockTestSet, priority: 1 }], 200, {
          'x-total-count': '1',
        }) as unknown as Response
      );

      const result = await client.getTestSets();

      // @ts-expect-error - priorityLevel is added by the client
      expect(result.data[0].priorityLevel).toBe('Medium');
    });

    it('converts numeric priority 0 to Low', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([{ ...mockTestSet, priority: 0 }], 200, {
          'x-total-count': '1',
        }) as unknown as Response
      );

      const result = await client.getTestSets();

      // @ts-expect-error - priorityLevel is added by the client
      expect(result.data[0].priorityLevel).toBe('Low');
    });

    it('converts numeric priority 2 to High', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([{ ...mockTestSet, priority: 2 }], 200, {
          'x-total-count': '1',
        }) as unknown as Response
      );

      const result = await client.getTestSets();

      // @ts-expect-error - priorityLevel is added by the client
      expect(result.data[0].priorityLevel).toBe('High');
    });

    it('sends Authorization header', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, {
          'x-total-count': '0',
        }) as unknown as Response
      );

      await client.getTestSets();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });

    it('handles missing x-total-count gracefully', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse([]) as unknown as Response);

      const result = await client.getTestSets();

      expect(result.pagination.totalCount).toBe(0);
    });
  });

  describe('getTestSet', () => {
    it('fetches a single test set by identifier', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockTestSet) as unknown as Response
      );

      const result = await client.getTestSet('ts-1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_sets/ts-1'),
        expect.anything()
      );
      expect(result.id).toBe('ts-1');
    });

    it('converts priority on single fetch', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({
          ...mockTestSet,
          priority: 3,
        }) as unknown as Response
      );

      const result = await client.getTestSet('ts-1');

      // @ts-expect-error - priorityLevel is added by the client
      expect(result.priorityLevel).toBe('Urgent');
    });

    it('throws on 404', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404) as unknown as Response
      );

      await expect(client.getTestSet('missing')).rejects.toThrow(
        'API error: 404'
      );
    });
  });

  describe('createTestSet', () => {
    it('sends POST to /test_sets with test set data', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockTestSet) as unknown as Response
      );

      await client.createTestSet({ name: 'My Test Set' });

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_sets'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"name":"My Test Set"'),
        })
      );
    });

    it('returns the created test set', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockTestSet) as unknown as Response
      );

      const result = await client.createTestSet({ name: 'My Test Set' });

      expect(result.id).toBe('ts-1');
      expect(result.name).toBe('My Test Set');
    });
  });

  describe('updateTestSet', () => {
    it('sends PUT to /test_sets/{id}', async () => {
      const updated = { ...mockTestSet, name: 'Updated' };
      fetchMock.mockResolvedValue(
        makeFetchResponse(updated) as unknown as Response
      );

      const result = await client.updateTestSet('ts-1', { name: 'Updated' });

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_sets/ts-1'),
        expect.objectContaining({
          method: 'PUT',
          body: expect.stringContaining('"name":"Updated"'),
        })
      );
      expect(result.name).toBe('Updated');
    });
  });

  describe('deleteTestSet', () => {
    it('sends DELETE to /test_sets/{id}', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(null) as unknown as Response
      );

      await client.deleteTestSet('ts-1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/test_sets/ts-1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('throws on 500', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(
          { detail: 'Server error' },
          500
        ) as unknown as Response
      );

      await expect(client.deleteTestSet('ts-1')).rejects.toThrow(
        'API error: 500'
      );
    });
  });

  describe('error handling', () => {
    it('throws network error with descriptive message', async () => {
      fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

      await expect(client.getTestSet('ts-1')).rejects.toThrow(
        expect.objectContaining({
          message: expect.stringContaining('Network error'),
        })
      );
    });
  });
});
