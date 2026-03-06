import { CategoryClient } from '../category-client';
import { UUID } from 'crypto';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';
const CATEGORY_ID = 'c1c1c1c1-0000-0000-0000-000000000001' as UUID;

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

describe('CategoryClient', () => {
  let client: CategoryClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new CategoryClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  it('fetches categories with default params', async () => {
    fetchMock.mockResolvedValue(makeFetch([{ id: 'cat-1' }]));
    const result = await client.getCategories();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/categories`),
      expect.any(Object)
    );
    expect(result).toHaveLength(1);
  });

  it('includes entity_type in URL when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getCategories({ entity_type: 'Test' });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('entity_type=Test');
  });

  it('includes $filter in URL when provided', async () => {
    fetchMock.mockResolvedValue(makeFetch([]));
    await client.getCategories({ $filter: "name eq 'Safety'" });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('%24filter');
  });

  it('fetches a single category by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: CATEGORY_ID }));
    await client.getCategory(CATEGORY_ID);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/categories/${CATEGORY_ID}`),
      expect.any(Object)
    );
  });

  it('creates a category with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-cat' }));
    const payload = { name: 'New Category' };
    await client.createCategory(payload as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/categories');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject(payload);
  });

  it('updates a category with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: CATEGORY_ID }));
    await client.updateCategory(CATEGORY_ID, { name: 'Updated' } as never);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/categories/${CATEGORY_ID}`);
    expect(opts.method).toBe('PUT');
  });

  it('deletes a category with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: CATEGORY_ID }));
    await client.deleteCategory(CATEGORY_ID);
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/categories/${CATEGORY_ID}`);
    expect(opts.method).toBe('DELETE');
  });
});
