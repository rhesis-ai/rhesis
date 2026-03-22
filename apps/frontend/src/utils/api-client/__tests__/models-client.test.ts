import { ModelsClient } from '../models-client';
import { UUID } from 'crypto';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';
const MODEL_ID = 'mo1mo1m0-0000-0000-0000-000000000001' as UUID;

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

describe('ModelsClient', () => {
  let client: ModelsClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new ModelsClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches paginated models with default params', async () => {
    fetchMock.mockResolvedValue(
      makeFetch([{ id: 'mo1' }], 200, { 'x-total-count': '1' })
    );
    const result = await client.getModels();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/models`),
      expect.any(Object)
    );
    expect(result.data).toHaveLength(1);
    expect(result.pagination.totalCount).toBe(1);
  });

  it('fetches a single model by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: MODEL_ID }));
    await client.getModel(MODEL_ID);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/models/${MODEL_ID}`),
      expect.any(Object)
    );
  });

  it('creates a model with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-mo' }));
    const payload = { name: 'GPT-4' };
    await client.createModel(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/models');
    expect(opts.method).toBe('POST');
  });

  it('tests model connection with POST to /models/:id/test', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ status: 'ok', message: 'Connected' })
    );
    await client.testModelConnection(MODEL_ID);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/models/${MODEL_ID}/test`);
    expect(opts.method).toBe('POST');
  });

  it('gets provider models', async () => {
    fetchMock.mockResolvedValue(makeFetch(['gpt-4', 'gpt-3.5']));
    const result = await client.getProviderModels('openai');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/models/provider/openai'),
      expect.any(Object)
    );
    expect(result).toEqual(['gpt-4', 'gpt-3.5']);
  });

  it('gets provider embedding models', async () => {
    fetchMock.mockResolvedValue(makeFetch(['text-embedding-3-small']));
    await client.getProviderEmbeddingModels('openai');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/models/provider/openai/embeddings'),
      expect.any(Object)
    );
  });
});
