import { useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileResponse,
  FileEntityType,
} from '@/utils/api-client/interfaces/file';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { EntityType } from '@/types/entity-type';
import { fileKeys } from '@/constants/query-keys';

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
  const notifications = useNotifications();
  const queryClient = useQueryClient();
  const queryKey = fileKeys.list(entityType, entityId);

  const {
    data: files = [],
    isLoading,
    isError,
    refetch,
  } = useQuery<FileResponse[]>({
    queryKey,
    queryFn: async () => {
      const filesClient = new ApiClientFactory(sessionToken).getFilesClient();
      if (entityType === EntityType.TEST) {
        return filesClient.getTestFiles(entityId);
      }
      if (entityType === EntityType.TEST_RESULT) {
        return filesClient.getTestResultFiles(entityId);
      }
      return [];
    },
    enabled: !!sessionToken && !!entityId,
  });

  const error = isError ? 'Failed to fetch files' : null;

  useEffect(() => {
    if (isError) {
      notifications.show('Failed to fetch files', {
        severity: 'error',
        autoHideDuration: 3000,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isError]);

  const uploadMutation = useMutation({
    mutationFn: (newFiles: File[]) => {
      if (!sessionToken) {
        throw new Error('No session token available');
      }
      return new ApiClientFactory(sessionToken)
        .getFilesClient()
        .uploadFiles(newFiles, entityId, entityType);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (fileId: string) => {
      if (!sessionToken) {
        throw new Error('No session token available');
      }
      return new ApiClientFactory(sessionToken)
        .getFilesClient()
        .deleteFile(fileId);
    },
  });

  const uploadFiles = useCallback(
    async (newFiles: File[]) => {
      try {
        const uploaded = await uploadMutation.mutateAsync(newFiles);
        queryClient.setQueryData<FileResponse[]>(queryKey, prev => [
          ...(prev ?? []),
          ...uploaded,
        ]);
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
    [uploadMutation, queryClient, queryKey, notifications]
  );

  const deleteFile = useCallback(
    async (fileId: string) => {
      try {
        await deleteMutation.mutateAsync(fileId);
        queryClient.setQueryData<FileResponse[]>(queryKey, prev =>
          (prev ?? []).filter(f => f.id !== fileId)
        );
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
    [deleteMutation, queryClient, queryKey, notifications]
  );

  const totalSizeBytes = files.reduce((sum, f) => sum + f.size_bytes, 0);

  return {
    files,
    isLoading,
    error,
    totalSizeBytes,
    uploadFiles,
    deleteFile,
    refetch,
  };
}
