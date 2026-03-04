/* eslint-disable @typescript-eslint/no-explicit-any */
import { renderHook, waitFor } from '@testing-library/react';
import { useFiles } from '../useFiles';
import { ApiClientFactory } from '../../utils/api-client/client-factory';

// Mock dependencies
jest.mock('../../utils/api-client/client-factory');
const mockShow = jest.fn();
const mockNotifications = { show: mockShow };
jest.mock('../../components/common/NotificationContext', () => ({
  useNotifications: () => mockNotifications,
}));

const mockApiClientFactory = ApiClientFactory as jest.MockedClass<
  typeof ApiClientFactory
>;

describe('useFiles', () => {
  const mockProps = {
    entityId: 'test-123',
    entityType: 'Test' as const,
    sessionToken: 'mock-session-token',
  };

  const mockFilesClient = {
    getTestFiles: jest.fn(),
    uploadFiles: jest.fn(),
    deleteFile: jest.fn(),
    getFileMetadata: jest.fn(),
    getFileContent: jest.fn(),
    getFileContentUrl: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockApiClientFactory.mockImplementation(
      () =>
        ({
          getFilesClient: () => mockFilesClient,
        }) as any
    );
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('initialization', () => {
    it('starts with initial state', () => {
      mockFilesClient.getTestFiles.mockResolvedValue([]);
      const { result } = renderHook(() => useFiles(mockProps));

      expect(result.current.files).toEqual([]);
      expect(result.current.isLoading).toBe(true);
      expect(result.current.error).toBe(null);
      expect(result.current.totalSizeBytes).toBe(0);
    });

    it('fetches files on mount', async () => {
      const mockFiles = [
        {
          id: 'file-1',
          filename: 'test.png',
          content_type: 'image/png',
          size_bytes: 1024,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 0,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ];

      mockFilesClient.getTestFiles.mockResolvedValue(mockFiles);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFilesClient.getTestFiles).toHaveBeenCalledWith('test-123');
      expect(result.current.files).toEqual(mockFiles);
      expect(result.current.error).toBe(null);
    });
  });

  describe('fetchFiles', () => {
    it('handles successful file fetch', async () => {
      const mockFiles = [
        {
          id: 'file-1',
          filename: 'image.png',
          content_type: 'image/png',
          size_bytes: 2048,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 0,
        },
        {
          id: 'file-2',
          filename: 'document.pdf',
          content_type: 'application/pdf',
          size_bytes: 4096,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 1,
        },
      ];

      mockFilesClient.getTestFiles.mockResolvedValue(mockFiles);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.files).toEqual(mockFiles);
      expect(result.current.totalSizeBytes).toBe(6144);
      expect(result.current.error).toBe(null);
    });

    it('handles fetch error', async () => {
      const error = new Error('Failed to fetch');
      mockFilesClient.getTestFiles.mockRejectedValue(error);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Failed to fetch files');
      expect(result.current.files).toEqual([]);
    });

    it('handles missing session token', async () => {
      const { result } = renderHook(() =>
        useFiles({ ...mockProps, sessionToken: '' })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFilesClient.getTestFiles).not.toHaveBeenCalled();
    });

    it('handles missing entityId', async () => {
      const { result } = renderHook(() =>
        useFiles({ ...mockProps, entityId: '' })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFilesClient.getTestFiles).not.toHaveBeenCalled();
    });
  });

  describe('uploadFiles', () => {
    it('uploads files successfully', async () => {
      mockFilesClient.getTestFiles.mockResolvedValue([]);

      const uploadedFiles = [
        {
          id: 'file-new',
          filename: 'new-image.png',
          content_type: 'image/png',
          size_bytes: 5000,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 0,
        },
      ];
      mockFilesClient.uploadFiles.mockResolvedValue(uploadedFiles);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const file = new File(['test content'], 'new-image.png', {
        type: 'image/png',
      });

      let uploadResult: any;
      await waitFor(async () => {
        uploadResult = await result.current.uploadFiles([file]);
      });

      expect(mockFilesClient.uploadFiles).toHaveBeenCalledWith(
        [file],
        'test-123',
        'Test'
      );
      expect(uploadResult).toEqual(uploadedFiles);

      await waitFor(() => {
        expect(result.current.files).toEqual(uploadedFiles);
      });
    });

    it('appends uploaded files to existing files', async () => {
      const existingFiles = [
        {
          id: 'file-1',
          filename: 'existing.png',
          content_type: 'image/png',
          size_bytes: 1000,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 0,
        },
      ];
      mockFilesClient.getTestFiles.mockResolvedValue(existingFiles);

      const newUploadedFiles = [
        {
          id: 'file-2',
          filename: 'new.pdf',
          content_type: 'application/pdf',
          size_bytes: 2000,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 1,
        },
      ];
      mockFilesClient.uploadFiles.mockResolvedValue(newUploadedFiles);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.files).toHaveLength(1);
      });

      const file = new File(['pdf'], 'new.pdf', { type: 'application/pdf' });
      await waitFor(async () => {
        await result.current.uploadFiles([file]);
      });

      await waitFor(() => {
        expect(result.current.files).toHaveLength(2);
      });
    });

    it('handles upload error', async () => {
      mockFilesClient.getTestFiles.mockResolvedValue([]);
      const error = new Error('Upload failed') as Error & {
        data?: { detail?: string };
      };
      error.data = { detail: 'File too large' };
      mockFilesClient.uploadFiles.mockRejectedValue(error);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const file = new File(['big'], 'big.png', { type: 'image/png' });

      await expect(result.current.uploadFiles([file])).rejects.toThrow();

      expect(mockShow).toHaveBeenCalledWith('File too large', {
        severity: 'error',
        autoHideDuration: 5000,
      });
    });

    it('handles missing session token for upload', async () => {
      const { result } = renderHook(() =>
        useFiles({ ...mockProps, sessionToken: '' })
      );

      await expect(
        result.current.uploadFiles([
          new File(['x'], 'x.png', { type: 'image/png' }),
        ])
      ).rejects.toThrow('No session token available');
    });
  });

  describe('deleteFile', () => {
    it('deletes a file successfully', async () => {
      const existingFiles = [
        {
          id: 'file-1',
          filename: 'to-delete.png',
          content_type: 'image/png',
          size_bytes: 1024,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 0,
        },
        {
          id: 'file-2',
          filename: 'keep.pdf',
          content_type: 'application/pdf',
          size_bytes: 2048,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 1,
        },
      ];

      mockFilesClient.getTestFiles.mockResolvedValue(existingFiles);
      mockFilesClient.deleteFile.mockResolvedValue(existingFiles[0]);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.files).toHaveLength(2);
      });

      await waitFor(async () => {
        await result.current.deleteFile('file-1');
      });

      expect(mockFilesClient.deleteFile).toHaveBeenCalledWith('file-1');

      await waitFor(() => {
        expect(result.current.files).toHaveLength(1);
        expect(result.current.files[0].id).toBe('file-2');
      });
    });

    it('handles delete error', async () => {
      mockFilesClient.getTestFiles.mockResolvedValue([]);
      const error = new Error('Failed to delete');
      mockFilesClient.deleteFile.mockRejectedValue(error);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await expect(result.current.deleteFile('file-1')).rejects.toThrow(
        'Failed to delete'
      );

      expect(mockShow).toHaveBeenCalledWith('Failed to delete file', {
        severity: 'error',
        autoHideDuration: 3000,
      });
    });

    it('handles missing session token for delete', async () => {
      const { result } = renderHook(() =>
        useFiles({ ...mockProps, sessionToken: '' })
      );

      await expect(result.current.deleteFile('file-1')).rejects.toThrow(
        'No session token available'
      );
    });
  });

  describe('refetch', () => {
    it('refetches files when refetch is called', async () => {
      mockFilesClient.getTestFiles.mockResolvedValue([]);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      mockFilesClient.getTestFiles.mockClear();

      await waitFor(async () => {
        await result.current.refetch();
      });

      expect(mockFilesClient.getTestFiles).toHaveBeenCalledTimes(1);
      expect(mockFilesClient.getTestFiles).toHaveBeenCalledWith('test-123');
    });
  });

  describe('totalSizeBytes', () => {
    it('computes total size from all files', async () => {
      const files = [
        {
          id: 'f1',
          filename: 'a.png',
          content_type: 'image/png',
          size_bytes: 1000,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 0,
        },
        {
          id: 'f2',
          filename: 'b.pdf',
          content_type: 'application/pdf',
          size_bytes: 3000,
          entity_id: 'test-123',
          entity_type: 'Test',
          position: 1,
        },
      ];

      mockFilesClient.getTestFiles.mockResolvedValue(files);

      const { result } = renderHook(() => useFiles(mockProps));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.totalSizeBytes).toBe(4000);
    });
  });
});
