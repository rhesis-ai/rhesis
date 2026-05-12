/**
 * TanStack Query hooks for file metadata, thumbnails, and content URLs.
 *
 * These hooks replace the manual useEffect + blob-URL pattern in
 * FileAttachmentList, ConversationHistory, SpanDetailsPanel, etc.
 */
'use client';

import { useEffect, useState } from 'react';
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
// useFileThumbnail — fetches the thumbnail Blob from /files/{id}/thumbnail.
//
// IMPORTANT: This hook intentionally returns the `Blob` (not an object URL).
// TanStack Query's `gcTime` only evicts the cache entry; it never calls
// `URL.revokeObjectURL()`. If we created object URLs inside the queryFn
// they would accumulate as the user navigated, leaking memory.
//
// Consumers should turn the Blob into an object URL inside a `useEffect`
// and revoke it on cleanup — see `useThumbnailObjectUrl` below for the
// canonical pattern.
// ---------------------------------------------------------------------------
export function useFileThumbnail(
  fileId: string | null,
  size: 72 | 144 | 288 = 144,
  sessionToken: string
) {
  return useQuery<Blob>({
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
      return response.blob();
    },
    gcTime: 10 * 60_000,
  });
}

// ---------------------------------------------------------------------------
// useThumbnailObjectUrl — render-side helper that turns the cached Blob into
// a short-lived object URL and revokes it on unmount / Blob change.
//
// This is the safe consumer pattern for `useFileThumbnail`. Keep this
// alongside the hook so future consumers don't reinvent the wheel.
// ---------------------------------------------------------------------------
export function useThumbnailObjectUrl(blob: Blob | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!blob) {
      setUrl(null);
      return;
    }
    const objectUrl = URL.createObjectURL(blob);
    setUrl(objectUrl);
    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [blob]);

  return url;
}

// ---------------------------------------------------------------------------
// useFileContentUrl — returns the direct /files/{id}/content URL (no fetch).
// The browser follows the 302 to the presigned URL automatically.
// ---------------------------------------------------------------------------
export function useFileContentUrl(fileId: string | null): string | null {
  if (!fileId) return null;
  return `/api/files/${fileId}/content`;
}
