import { useState, useCallback, useEffect } from 'react';
import {
  FileResponse,
  FileEntityType,
} from '@/utils/api-client/interfaces/file';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';

interface UseFilesProps {
  entityId: string;
  entityType: FileEntityType;
  sessionToken: string;
}

export function useFiles({
  entityId,
  entityType,
  sessionToken,
}: UseFilesProps) {
  const [files, setFiles] = useState<FileResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const notifications = useNotifications();

  const fetchFiles = useCallback(async () => {
    if (!sessionToken || !entityId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const clientFactory = new ApiClientFactory(sessionToken);
      const filesClient = clientFactory.getFilesClient();

      let fetched: FileResponse[];
      if (entityType === 'Test') {
        fetched = await filesClient.getTestFiles(entityId);
      } else if (entityType === 'TestResult') {
        fetched = await filesClient.getTestResultFiles(entityId);
      } else {
        fetched = [];
      }
      setFiles(fetched);
    } catch (_err) {
      setError('Failed to fetch files');
      notifications.show('Failed to fetch files', {
        severity: 'error',
        autoHideDuration: 3000,
      });
    } finally {
      setIsLoading(false);
    }
  }, [entityId, entityType, sessionToken, notifications]);

  const uploadFiles = useCallback(
    async (newFiles: File[]) => {
      if (!sessionToken) {
        throw new Error('No session token available');
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const filesClient = clientFactory.getFilesClient();
        const uploaded = await filesClient.uploadFiles(
          newFiles,
          entityId,
          entityType
        );
        setFiles(prev => [...prev, ...uploaded]);
        notifications.show(
          `${uploaded.length} file${uploaded.length > 1 ? 's' : ''} uploaded`,
          { severity: 'success', autoHideDuration: 3000 }
        );
        return uploaded;
      } catch (err) {
        const message =
          (err as Error & { data?: { detail?: string } })?.data?.detail ??
          'Failed to upload files';
        notifications.show(message, {
          severity: 'error',
          autoHideDuration: 5000,
        });
        throw err;
      }
    },
    [entityId, entityType, sessionToken, notifications]
  );

  const deleteFile = useCallback(
    async (fileId: string) => {
      if (!sessionToken) {
        throw new Error('No session token available');
      }

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const filesClient = clientFactory.getFilesClient();
        await filesClient.deleteFile(fileId);
        setFiles(prev => prev.filter(f => f.id !== fileId));
        notifications.show('File deleted', {
          severity: 'neutral',
          autoHideDuration: 3000,
        });
      } catch (err) {
        notifications.show('Failed to delete file', {
          severity: 'error',
          autoHideDuration: 3000,
        });
        throw err;
      }
    },
    [sessionToken, notifications]
  );

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const totalSizeBytes = files.reduce((sum, f) => sum + f.size_bytes, 0);

  return {
    files,
    isLoading,
    error,
    totalSizeBytes,
    uploadFiles,
    deleteFile,
    refetch: fetchFiles,
  };
}
