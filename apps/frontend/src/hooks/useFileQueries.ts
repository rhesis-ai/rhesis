/**
 * TanStack Query hooks for file metadata, thumbnails, and content URLs.
 *
 * These hooks replace the manual useEffect + blob-URL pattern in
 * FileAttachmentList, ConversationHistory, SpanDetailsPanel, etc.
 */
'use client';

import { useQuery } from '@tanstack/react-query';
import { FileResponse } from '@/utils/api-client/interfaces/file';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

// ApiClientFactory is an instance-based factory (no static helpers). We
// instantiate it per-token so the cached, lazy ``getFilesClient()`` accessor
// is the one issuing requests.

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------
export const fileKeys = {
  all: ['files'] as const,
  metadata: (fileId: string) => [...fileKeys.all, 'metadata', fileId] as const,
  thumbnail: (fileId: string, size: number) =>
    [...fileKeys.all, 'thumbnail', fileId, size] as const,
  contentUrl: (fileId: string) =>
    [...fileKeys.all, 'contentUrl', fileId] as const,
};

// ---------------------------------------------------------------------------
// useFileMetadata — cached file metadata from GET /files/{id}
// ---------------------------------------------------------------------------
export function useFileMetadata(fileId: string | null, sessionToken: string) {
  return useQuery<FileResponse>({
    queryKey: fileKeys.metadata(fileId ?? ''),
    enabled: !!fileId && !!sessionToken,
    queryFn: async () => {
      const client = new ApiClientFactory(sessionToken).getFilesClient();
      return client.getFileMetadata(fileId!);
    },
  });
}

// ---------------------------------------------------------------------------
// useFileThumbnail — resolves to an object URL for the thumbnail endpoint
//
// The hook fetches /files/{id}/thumbnail?size={size} with credentials and
// creates a blob URL.  The blob URL is revoked when the cache entry is
// garbage-collected.
// ---------------------------------------------------------------------------
export function useFileThumbnail(
  fileId: string | null,
  size: 72 | 144 | 288 = 144,
  sessionToken: string
) {
  return useQuery<string>({
    queryKey: fileKeys.thumbnail(fileId ?? '', size),
    enabled: !!fileId && !!sessionToken,
    queryFn: async () => {
      const response = await fetch(
        `/api/files/${fileId}/thumbnail?size=${size}`,
        {
          headers: { Authorization: `Bearer ${sessionToken}` },
          credentials: 'include',
          redirect: 'follow',
        }
      );
      if (!response.ok)
        throw new Error(`Thumbnail fetch failed: ${response.status}`);
      const blob = await response.blob();
      return URL.createObjectURL(blob);
    },
    // Revoke the blob URL when the entry is removed from cache
    gcTime: 10 * 60_000,
  });
}

// ---------------------------------------------------------------------------
// useFileContentUrl — returns the direct /files/{id}/content URL (no fetch).
// The browser follows the 302 to the presigned URL automatically.
// ---------------------------------------------------------------------------
export function useFileContentUrl(fileId: string | null): string | null {
  if (!fileId) return null;
  return `/api/files/${fileId}/content`;
}
