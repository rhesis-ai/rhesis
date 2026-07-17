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
import { fileKeys } from '@/constants/query-keys';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';

// ---------------------------------------------------------------------------
// useFileMetadata — cached file metadata from GET /files/{id}
// ---------------------------------------------------------------------------
export function useFileMetadata(fileId: string | null) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<FileResponse>({
    queryKey: fileKeys.metadata(fileId ?? ''),
    enabled: !!fileId && isAuthenticated,
    queryFn: async () => {
      if (!fileId) {
        throw new Error('fileId is required to fetch file metadata');
      }
      const client = new ApiClientFactory().getFilesClient();
      return client.getFileMetadata(fileId);
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
  size: 72 | 144 | 288 = 144
) {
  const isAuthenticated = useIsAuthenticated();
  return useQuery<Blob>({
    queryKey: fileKeys.thumbnail(fileId ?? '', size),
    enabled: !!fileId && isAuthenticated,
    queryFn: async () => {
      // Same-origin BFF proxy: it injects Authorization server-side from the
      // httpOnly session cookie. The plain `/api/files/...` catch-all only
      // FORWARDS a browser-supplied header — which no longer exists, since
      // the access token never reaches browser JS.
      const response = await fetch(
        `/api/backend/files/${fileId}/thumbnail?size=${size}`,
        {
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
// useFileContentUrl — returns the /files/{id}/content URL via the BFF proxy
// (no fetch). The proxy authenticates the request server-side; a cross-origin
// (presigned storage) redirect passes through for the browser to follow.
// ---------------------------------------------------------------------------
export function useFileContentUrl(fileId: string | null): string | null {
  if (!fileId) return null;
  return `/api/backend/files/${fileId}/content`;
}
