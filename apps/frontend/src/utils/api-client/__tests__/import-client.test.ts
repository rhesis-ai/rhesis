import { ImportClient } from '../import-client';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';

function makeFetch(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: () => null,
      entries: () => [],
    },
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response);
}

describe('ImportClient', () => {
  let client: ImportClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new ImportClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  // -------------------------------------------------------------------------
  // analyzeFile (Step 1)
  // -------------------------------------------------------------------------

  it('uploads a file with multipart/form-data to /import/analyze', async () => {
    fetchMock.mockResolvedValue(makeFetch({ import_id: 'imp1', columns: [] }));
    const file = new File(['col1,col2\nv1,v2'], 'test.csv', {
      type: 'text/csv',
    });

    const result = await client.analyzeFile(file);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/import/analyze`),
      expect.objectContaining({ method: 'POST' })
    );
    const opts = fetchMock.mock.calls[0][1];
    expect(opts.body).toBeInstanceOf(FormData);
    expect(result.import_id).toBe('imp1');
  });

  it('throws an error with status and detail when analyzeFile fails', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ detail: 'Invalid file format' }, 422)
    );

    await expect(client.analyzeFile(new File([''], 'bad.txt'))).rejects.toThrow(
      'Upload failed'
    );
  });

  // -------------------------------------------------------------------------
  // parseWithMapping (Step 2)
  // -------------------------------------------------------------------------

  it('sends mapping and test_type to /import/:id/parse', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ import_id: 'imp1', row_count: 10 })
    );

    await client.parseWithMapping('imp1', { prompt: 'col1' });

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/import/imp1/parse');
    expect(opts.method).toBe('POST');
    const body = JSON.parse(opts.body);
    expect(body.mapping).toEqual({ prompt: 'col1' });
    expect(body.test_type).toBe('Single-Turn');
  });

  it('accepts a custom testType in parseWithMapping', async () => {
    fetchMock.mockResolvedValue(makeFetch({ import_id: 'imp1', row_count: 5 }));

    await client.parseWithMapping('imp1', {}, 'Multi-Turn');

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.test_type).toBe('Multi-Turn');
  });

  // -------------------------------------------------------------------------
  // getPreviewPage (Step 3)
  // -------------------------------------------------------------------------

  it('fetches a preview page with page and page_size params', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ items: [], total: 0, page: 1, page_size: 50 })
    );

    await client.getPreviewPage('imp1', 2, 25);

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/import/imp1/preview');
    expect(calledUrl).toContain('page=2');
    expect(calledUrl).toContain('page_size=25');
  });

  // -------------------------------------------------------------------------
  // confirmImport (Step 4)
  // -------------------------------------------------------------------------

  it('sends a POST to /import/:id/confirm', async () => {
    fetchMock.mockResolvedValue(makeFetch({ test_set_id: 'ts1' }));

    await client.confirmImport('imp1', { name: 'My Set' });

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/import/imp1/confirm');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject({ name: 'My Set' });
  });

  // -------------------------------------------------------------------------
  // cancelImport (Step 5)
  // -------------------------------------------------------------------------

  it('sends a DELETE to /import/:id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ cancelled: true }));

    await client.cancelImport('imp1');

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/import/imp1');
    expect(opts.method).toBe('DELETE');
  });

  // -------------------------------------------------------------------------
  // remapWithLlm
  // -------------------------------------------------------------------------

  it('sends a POST to /import/:id/remap', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ mapping: {}, llm_available: true })
    );

    await client.remapWithLlm('imp1');

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/import/imp1/remap');
    expect(opts.method).toBe('POST');
  });
});
