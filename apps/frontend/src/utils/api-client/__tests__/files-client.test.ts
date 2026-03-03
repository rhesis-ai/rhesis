import { FilesClient } from '../files-client';

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
    blob: () =>
      Promise.resolve(new Blob([JSON.stringify(body)], { type: 'image/png' })),
  } as unknown as Response);
}

describe('FilesClient', () => {
  let client: FilesClient;
  let fetchMock: jest.Mock;

  beforeEach(() => {
    client = new FilesClient('test-token');
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('uploadFiles', () => {
    it('sends multipart POST with files, entity_id, and entity_type', async () => {
      const mockResponse = [
        {
          id: 'file-1',
          filename: 'test.png',
          content_type: 'image/png',
          size_bytes: 1024,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 0,
        },
      ];

      fetchMock.mockResolvedValue({
        ok: true,
        status: 201,
        json: () => Promise.resolve(mockResponse),
      });

      const file = new File(['image data'], 'test.png', {
        type: 'image/png',
      });
      const result = await client.uploadFiles([file], 'test-123', 'Test');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/files'),
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );

      // Verify entity_id and entity_type are in query params
      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('entity_id=test-123');
      expect(calledUrl).toContain('entity_type=Test');

      // Verify FormData was sent with files only
      const callArgs = fetchMock.mock.calls[0][1];
      expect(callArgs.body).toBeInstanceOf(FormData);

      const formData = callArgs.body as FormData;
      expect(formData.get('entity_id')).toBeNull();
      expect(formData.get('files')).toBeInstanceOf(File);

      expect(result).toEqual(mockResponse);
    });

    it('sends multiple files in FormData', async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        status: 201,
        json: () => Promise.resolve([]),
      });

      const files = [
        new File(['a'], 'a.png', { type: 'image/png' }),
        new File(['b'], 'b.pdf', { type: 'application/pdf' }),
      ];

      await client.uploadFiles(files, 'test-123', 'Test');

      const formData = fetchMock.mock.calls[0][1].body as FormData;
      const formFiles = formData.getAll('files');
      expect(formFiles).toHaveLength(2);

      // entity fields are in query params, not form data
      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain('entity_id=test-123');
    });

    it('throws error on upload failure', async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 413,
        json: () => Promise.resolve({ detail: 'File too large' }),
      });

      const file = new File(['big'], 'big.png', { type: 'image/png' });

      await expect(
        client.uploadFiles([file], 'test-123', 'Test')
      ).rejects.toThrow('File upload failed');
    });

    it('handles non-JSON error response', async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('not json')),
      });

      const file = new File(['x'], 'x.png', { type: 'image/png' });

      await expect(
        client.uploadFiles([file], 'test-123', 'Test')
      ).rejects.toThrow('File upload failed');
    });

    it('omits Content-Type header for multipart boundary', async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        status: 201,
        json: () => Promise.resolve([]),
      });

      const file = new File(['x'], 'x.png', { type: 'image/png' });
      await client.uploadFiles([file], 'test-123', 'Test');

      const headers = fetchMock.mock.calls[0][1].headers;
      expect(headers['Content-Type']).toBeUndefined();
    });
  });

  describe('getFileMetadata', () => {
    it('fetches file metadata by id', async () => {
      const mockFile = {
        id: 'file-abc',
        filename: 'doc.pdf',
        content_type: 'application/pdf',
        size_bytes: 4096,
      };

      fetchMock.mockResolvedValue(
        makeFetchResponse(mockFile) as unknown as Response
      );

      const result = await client.getFileMetadata('file-abc');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/files/file-abc'),
        expect.objectContaining({ credentials: 'include' })
      );
      expect(result.filename).toBe('doc.pdf');
    });
  });

  describe('getFileContentUrl', () => {
    it('returns the correct content URL', () => {
      const url = client.getFileContentUrl('file-xyz');
      expect(url).toBe(`${BASE_URL}/files/file-xyz/content`);
    });
  });

  describe('getFileContent', () => {
    it('fetches file content as blob with auth headers', async () => {
      const mockBlob = new Blob(['png data'], { type: 'image/png' });
      fetchMock.mockResolvedValue({
        ok: true,
        blob: () => Promise.resolve(mockBlob),
      });

      const result = await client.getFileContent('file-img');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/files/file-img/content'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
          credentials: 'include',
        })
      );
      expect(result).toBe(mockBlob);
    });

    it('throws error on failed content fetch', async () => {
      fetchMock.mockResolvedValue({
        ok: false,
        status: 404,
      });

      await expect(client.getFileContent('missing')).rejects.toThrow(
        'Failed to fetch file content'
      );
    });
  });

  describe('deleteFile', () => {
    it('sends DELETE request for the file', async () => {
      const deletedFile = {
        id: 'file-del',
        filename: 'removed.png',
        content_type: 'image/png',
        size_bytes: 512,
      };
      fetchMock.mockResolvedValue(
        makeFetchResponse(deletedFile) as unknown as Response
      );

      const result = await client.deleteFile('file-del');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/files/file-del'),
        expect.objectContaining({ method: 'DELETE' })
      );
      expect(result.id).toBe('file-del');
    });
  });

  describe('getTestFiles', () => {
    it('fetches files for a test', async () => {
      const mockFiles = [
        { id: 'f1', filename: 'a.png' },
        { id: 'f2', filename: 'b.pdf' },
      ];
      fetchMock.mockResolvedValue(
        makeFetchResponse(mockFiles) as unknown as Response
      );

      const result = await client.getTestFiles('test-456');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/tests/test-456/files'),
        expect.objectContaining({ credentials: 'include' })
      );
      expect(result).toHaveLength(2);
    });
  });

  describe('error handling', () => {
    it('throws error on 404', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse({ detail: 'Not found' }, 404) as unknown as Response
      );

      await expect(client.getFileMetadata('missing')).rejects.toThrow(
        'API error: 404'
      );
    });

    it('throws error on 500', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse(
          { detail: 'Server error' },
          500
        ) as unknown as Response
      );

      await expect(client.getTestFiles('test-1')).rejects.toThrow(
        'API error: 500'
      );
    });

    it('sends Authorization header', async () => {
      fetchMock.mockResolvedValue(
        makeFetchResponse([]) as unknown as Response
      );

      await client.getTestFiles('test-1');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }),
        })
      );
    });
  });
});
