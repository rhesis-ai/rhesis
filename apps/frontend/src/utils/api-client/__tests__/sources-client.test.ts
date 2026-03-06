import { SourcesClient } from '../sources-client';
import { UUID } from 'crypto';

const BASE_URL = 'http://127.0.0.1:8080/api/v1';
const SOURCE_ID = 'aaaaaaaa-0000-0000-0000-000000000001' as UUID;

function makeFetch(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
  contentType = 'application/json'
) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      get: (k: string) => {
        const map: Record<string, string> = {
          'content-type': contentType,
          ...headers,
        };
        return map[k.toLowerCase()] ?? null;
      },
      entries: () => Object.entries(headers),
    },
    json: () => Promise.resolve(body),
    text: () =>
      Promise.resolve(typeof body === 'string' ? body : JSON.stringify(body)),
    blob: () => Promise.resolve(new Blob([JSON.stringify(body)])),
  } as unknown as Response);
}

describe('SourcesClient', () => {
  let client: SourcesClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new SourcesClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => jest.restoreAllMocks());

  // -------------------------------------------------------------------------
  // getSources
  // -------------------------------------------------------------------------

  it('fetches sources with default pagination', async () => {
    fetchMock.mockResolvedValue(makeFetch([], 200, { 'x-total-count': '0' }));

    await client.getSources();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`${BASE_URL}/sources`),
      expect.any(Object)
    );
  });

  // -------------------------------------------------------------------------
  // getSource / getSourceWithContent
  // -------------------------------------------------------------------------

  it('fetches a single source by id', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: SOURCE_ID }));

    await client.getSource(SOURCE_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/sources/${SOURCE_ID}`),
      expect.any(Object)
    );
  });

  it('fetches a source with content via /content endpoint', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: SOURCE_ID, content: 'text' }));

    await client.getSourceWithContent(SOURCE_ID);

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain(`/sources/${SOURCE_ID}/content`);
  });

  // -------------------------------------------------------------------------
  // createSource / createSourceFromContent
  // -------------------------------------------------------------------------

  it('creates a source with POST', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-s' }));
    const payload = { title: 'My Doc', content: 'text' };

    await client.createSource(payload as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/sources');
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toMatchObject(payload);
  });

  it('createSourceFromContent builds the correct payload', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-s' }));

    await client.createSourceFromContent('Title', 'Body text', 'Desc', {
      url: 'http://example.com',
    });

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.title).toBe('Title');
    expect(body.content).toBe('Body text');
    expect(body.description).toBe('Desc');
    expect(body.source_metadata).toEqual({ url: 'http://example.com' });
  });

  // -------------------------------------------------------------------------
  // updateSource / deleteSource
  // -------------------------------------------------------------------------

  it('updates a source with PUT', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: SOURCE_ID }));

    await client.updateSource(SOURCE_ID, { title: 'New Title' } as never);

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain(`/sources/${SOURCE_ID}`);
    expect(opts.method).toBe('PUT');
  });

  it('deletes a source with DELETE', async () => {
    fetchMock.mockResolvedValue(makeFetch(null));

    await client.deleteSource(SOURCE_ID);

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe('DELETE');
  });

  // -------------------------------------------------------------------------
  // uploadSource (multipart, with validation-error parsing)
  // -------------------------------------------------------------------------

  it('uploads a file as FormData to /sources/upload', async () => {
    fetchMock.mockResolvedValue(makeFetch({ id: 'new-s' }));
    const file = new File(['content'], 'doc.pdf', { type: 'application/pdf' });

    await client.uploadSource(file, 'My Title', 'Some desc');

    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/sources/upload');
    expect(opts.method).toBe('POST');
    expect(opts.body).toBeInstanceOf(FormData);
  });

  it('throws Unauthorized on 401 from uploadSource', async () => {
    fetchMock.mockResolvedValue(
      makeFetch({ detail: 'Not authenticated' }, 401)
    );

    await expect(client.uploadSource(new File([''], 'f.txt'))).rejects.toThrow(
      'Unauthorized'
    );
  });

  it('throws Unauthorized on 403 from uploadSource', async () => {
    fetchMock.mockResolvedValue(makeFetch({ detail: 'Forbidden' }, 403));

    await expect(client.uploadSource(new File([''], 'f.txt'))).rejects.toThrow(
      'Unauthorized'
    );
  });

  it('parses validation-error array detail from uploadSource', async () => {
    const detail = [
      { loc: ['body', 'file'], msg: 'field required', type: 'missing' },
    ];
    fetchMock.mockResolvedValue(makeFetch({ detail }, 422));

    await expect(client.uploadSource(new File([''], 'f.txt'))).rejects.toThrow(
      'body.file: field required'
    );
  });

  // -------------------------------------------------------------------------
  // getSourceContent (text)
  // -------------------------------------------------------------------------

  it('fetches source content as text', async () => {
    fetchMock.mockResolvedValue(
      makeFetch('raw text content', 200, {}, 'text/plain')
    );

    const result = await client.getSourceContent(SOURCE_ID);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/sources/${SOURCE_ID}/file`),
      expect.any(Object)
    );
    expect(result).toBe('raw text content');
  });
});
