import { EndpointsClient } from '../endpoints-client';
import type { Endpoint } from '../interfaces/endpoint';

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

const mockEndpoint: Endpoint = {
  id: 'ep-1',
  name: 'Test Endpoint',
  connection_type: 'REST',
  environment: 'development',
  config_source: 'manual',
  response_format: 'json',
  method: 'POST',
  url: 'https://example.com/api',
};

describe('EndpointsClient', () => {
  let client: EndpointsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new EndpointsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('getEndpoints', () => {
    it('fetches endpoints with default pagination', async () => {
      const mockEndpoints = [mockEndpoint, { ...mockEndpoint, id: 'ep-2', name: 'Endpoint 2' }];
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockEndpoints, 200, { 'x-total-count': '2' })
      );

      const result = await client.getEndpoints();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/endpoints'),
        expect.objectContaining({ credentials: 'include' })
      );
      expect(result.data).toHaveLength(2);
      expect(result.pagination.totalCount).toBe(2);
    });

    it('sends Authorization header', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      await client.getEndpoints();

      expect(fetchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });

    it('respects custom pagination parameters', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      await client.getEndpoints({ skip: 20, limit: 10 });

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('skip=20');
      expect(calledUrl).toContain('limit=10');
    });

    it('returns empty data array and zero count when no endpoints', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([], 200, { 'x-total-count': '0' })
      );

      const result = await client.getEndpoints();

      expect(result.data).toHaveLength(0);
      expect(result.pagination.totalCount).toBe(0);
    });
  });

  describe('getEndpoint', () => {
    it('fetches a single endpoint by identifier', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse(mockEndpoint));

      const result = await client.getEndpoint('ep-1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/endpoints/ep-1'),
        expect.anything()
      );
      expect(result.id).toBe('ep-1');
      expect(result.name).toBe('Test Endpoint');
    });
  });

  describe('createEndpoint', () => {
    it('sends POST request with endpoint data', async () => {
      const newEndpointData = {
        name: 'New Endpoint',
        connection_type: 'REST' as const,
        environment: 'production' as const,
        config_source: 'manual' as const,
        response_format: 'json' as const,
        method: 'GET',
        url: 'https://api.example.com',
      };
      fetchMock.mockResolvedValue(
        makeFetchResponse({ id: 'ep-new', ...newEndpointData })
      );

      await client.createEndpoint(newEndpointData);

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/endpoints'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"name":"New Endpoint"'),
        })
      );
    });

    it('propagates errors thrown during create', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Validation error' }, 422)
      );

      await expect(
        client.createEndpoint({
          name: 'bad',
          connection_type: 'REST',
          environment: 'development',
          config_source: 'manual',
          response_format: 'json',
        })
      ).rejects.toThrow('API error: 422');
    });
  });

  describe('updateEndpoint', () => {
    it('sends PUT request with updated fields', async () => {
      const updateData = { name: 'Updated Endpoint', url: 'https://new.example.com' };
      fetchMock.mockResolvedValue(makeFetchResponse({ ...mockEndpoint, ...updateData }));

      await client.updateEndpoint('ep-1', updateData);

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/endpoints/ep-1'),
        expect.objectContaining({
          method: 'PUT',
          body: expect.stringContaining('"name":"Updated Endpoint"'),
        })
      );
    });
  });

  describe('deleteEndpoint', () => {
    it('sends DELETE request to correct URL', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse(null, 204));

      await client.deleteEndpoint('ep-1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/endpoints/ep-1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('invokeEndpoint', () => {
    it('sends POST request with input data', async () => {
      const inputData = { prompt: 'Hello world' };
      const responseData = { output: 'Response text' };
      fetchMock.mockResolvedValue(makeFetchResponse(responseData));

      const result = await client.invokeEndpoint('ep-1', inputData);

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/endpoints/ep-1/invoke'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"prompt":"Hello world"'),
        })
      );
      expect(result).toEqual(responseData);
    });
  });

  describe('executeEndpoint', () => {
    it('sends POST with test_set_ids array', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse({ test_run_id: 'run-1' }));

      await client.executeEndpoint('ep-1', ['set-1', 'set-2']);

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/endpoints/ep-1/execute'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"test_set_ids"'),
        })
      );
    });
  });

  describe('error handling', () => {
    it('throws on 404 when endpoint not found', async () => {
      fetchMock.mockResolvedValue(makeFetchResponse({ detail: 'Not found' }, 404));

      await expect(client.getEndpoint('nonexistent')).rejects.toThrow('API error: 404');
    });

    it('throws on 500 server error', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Internal Server Error' }, 500)
      );

      await expect(client.getEndpoints()).rejects.toThrow('API error: 500');
    });

    it('propagates network errors from single-item fetch', async () => {
      fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

      // getEndpoint uses this.fetch() which has network error wrapping
      await expect(client.getEndpoint('ep-1')).rejects.toThrow(
        expect.objectContaining({ message: expect.stringContaining('Network error') })
      );
    });
  });
});
