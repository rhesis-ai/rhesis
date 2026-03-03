import { BaseApiClient } from '../base-client';

// Concrete subclass to expose protected methods under test
class TestableClient extends BaseApiClient {
  async fetchPublic<T>(endpoint: string, options?: RequestInit): Promise<T> {
    return this.fetch<T>(endpoint, options);
  }

  async fetchPaginatedPublic<T>(
    endpoint: string,
    params: Record<string, unknown> = {},
    options?: RequestInit
  ) {
    return this.fetchPaginated<T>(
      endpoint,
      params as Parameters<typeof this.fetchPaginated>[1],
      options
    );
  }

  getHeadersPublic(): HeadersInit {
    return this.getHeaders();
  }

  extractTotalCountPublic(response: Response, defaultValue?: number): number {
    return this.extractTotalCount(response, defaultValue);
  }
}

function makeFetchResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {}
) {
  return {
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
  } as unknown as Response;
}

describe('BaseApiClient', () => {
  let client: TestableClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new TestableClient('test-session-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('getHeaders', () => {
    it('includes Content-Type application/json', () => {
      const headers = client.getHeadersPublic() as Record<string, string>;
      expect(headers['Content-Type']).toBe('application/json');
    });

    it('includes Authorization bearer token when session token provided', () => {
      const headers = client.getHeadersPublic() as Record<string, string>;
      expect(headers['Authorization']).toBe('Bearer test-session-token');
    });

    it('omits Authorization header when no session token', () => {
      const noAuthClient = new TestableClient();
      const headers = noAuthClient.getHeadersPublic() as Record<string, string>;
      expect(headers['Authorization']).toBeUndefined();
    });
  });

  describe('extractTotalCount', () => {
    it('parses x-total-count header as integer', () => {
      const response = makeFetchResponse([], 200, { 'x-total-count': '42' });
      expect(client.extractTotalCountPublic(response)).toBe(42);
    });

    it('returns 0 when header is absent', () => {
      const response = makeFetchResponse([]);
      expect(client.extractTotalCountPublic(response)).toBe(0);
    });

    it('returns custom default when header is absent', () => {
      const response = makeFetchResponse([]);
      expect(client.extractTotalCountPublic(response, 99)).toBe(99);
    });

    it('returns default when header value is not a number', () => {
      const response = makeFetchResponse([], 200, {
        'x-total-count': 'not-a-number',
      });
      expect(client.extractTotalCountPublic(response)).toBe(0);
    });
  });

  describe('fetch', () => {
    it('makes GET request to correct URL', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse({ id: '1' }));

      await client.fetchPublic('/tests/1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/tests/1'),
        expect.objectContaining({ credentials: 'include' })
      );
    });

    it('sends Authorization and Content-Type headers', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse({ id: '1' }));

      await client.fetchPublic('/tests/1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-session-token',
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('returns undefined for 204 No Content response', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse(null, 204));

      const result = await client.fetchPublic('/tests/1', { method: 'DELETE' });

      expect(result).toBeUndefined();
    });

    it('throws error with status on 404', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404, {
          'content-type': 'application/json',
        })
      );

      await expect(client.fetchPublic('/tests/missing')).rejects.toThrow(
        'API error: 404'
      );
    });

    it('throws error on 500 server error', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Server error' }, 500, {
          'content-type': 'application/json',
        })
      );

      await expect(client.fetchPublic('/tests/1')).rejects.toThrow(
        'API error: 500'
      );
    });

    it('wraps TypeError "Failed to fetch" as descriptive network error', async () => {
      fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

      await expect(client.fetchPublic('/tests/1')).rejects.toThrow(
        expect.objectContaining({
          message: expect.stringContaining('Network error'),
        })
      );
    });

    it('error includes status property for 404', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404, {
          'content-type': 'application/json',
        })
      );

      let caughtError: (Error & { status?: number }) | null = null;
      try {
        await client.fetchPublic('/tests/missing');
      } catch (e) {
        caughtError = e as Error & { status?: number };
      }

      expect(caughtError).not.toBeNull();
      expect(caughtError?.status).toBe(404);
    });

    it('includes POST body in request', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse({ id: 'new' }));

      await client.fetchPublic('/tests', {
        method: 'POST',
        body: JSON.stringify({ name: 'test' }),
      });

      expect(fetchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"name":"test"'),
        })
      );
    });

    it('parses detail array for validation errors (422)', async () => {
      const validationError = {
        detail: [{ loc: ['body', 'name'], msg: 'field required' }],
      };
      fetchMock.mockResolvedValue(
        makeFetchResponse(validationError, 422, {
          'content-type': 'application/json',
        })
      );

      await expect(
        client.fetchPublic('/tests', { method: 'POST' })
      ).rejects.toThrow(
        expect.objectContaining({
          message: expect.stringContaining('field required'),
        })
      );
    });
  });

  describe('fetchPaginated', () => {
    it('constructs paginated URL with skip/limit params', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      await client.fetchPaginatedPublic('/tests', { skip: 10, limit: 20 });

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('skip=10');
      expect(calledUrl).toContain('limit=20');
    });

    it('includes sort_by and sort_order in URL', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      await client.fetchPaginatedPublic('/tests', {
        sort_by: 'created_at',
        sort_order: 'asc',
      });

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('sort_by=created_at');
      expect(calledUrl).toContain('sort_order=asc');
    });

    it('returns correct pagination metadata', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(['item1', 'item2'], 200, {
          'x-total-count': '100',
        })
      );

      const result = await client.fetchPaginatedPublic<string>('/tests', {
        skip: 20,
        limit: 10,
      });

      expect(result.pagination.totalCount).toBe(100);
      expect(result.pagination.skip).toBe(20);
      expect(result.pagination.limit).toBe(10);
      expect(result.pagination.currentPage).toBe(2);
      expect(result.pagination.totalPages).toBe(10);
    });

    it('returns data array from response', async () => {
      const items = [{ id: '1' }, { id: '2' }, { id: '3' }];
      fetchMock.mockResolvedValue(
        makeFetchResponse(items, 200, { 'x-total-count': '3' })
      );

      const result = await client.fetchPaginatedPublic<{ id: string }>(
        '/items'
      );

      expect(result.data).toHaveLength(3);
      expect(result.data[0].id).toBe('1');
    });

    it('throws on non-ok response', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404, {
          'content-type': 'application/json',
        })
      );

      await expect(client.fetchPaginatedPublic('/tests')).rejects.toThrow(
        'API error: 404'
      );
    });
  });
});
