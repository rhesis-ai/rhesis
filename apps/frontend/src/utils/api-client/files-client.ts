import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import type { FileEntityType, FileResponse } from './interfaces/file';

export class FilesClient extends BaseApiClient {
  /**
   * Upload one or more files to an entity.
   * Uses multipart/form-data (browser sets Content-Type boundary automatically).
   */
  async uploadFiles(
    files: File[],
    entityId: string,
    entityType: FileEntityType
  ): Promise<FileResponse[]> {
    const url = new URL(`${this.baseUrl}${API_ENDPOINTS.files}`);
    url.searchParams.set('entity_id', entityId);
    url.searchParams.set('entity_type', entityType);

    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }

    // Omit Content-Type so browser sets multipart boundary
    const headers: Record<string, string> = {};
    if (this.sessionToken) {
      headers['Authorization'] = `Bearer ${this.sessionToken}`;
    }

    const response = await fetch(url.toString(), {
      method: 'POST',
      body: formData,
      headers,
      credentials: 'include',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      let detail = `File upload failed (${response.status})`;
      if (errorData?.detail) {
        if (typeof errorData.detail === 'string') {
          detail = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          detail = errorData.detail
            .map((e: { msg?: string; loc?: unknown[] }) =>
              e.msg ?? JSON.stringify(e)
            )
            .join('; ');
        }
      }
      const err = new Error('File upload failed') as Error & {
        status?: number;
        data?: { detail: string };
      };
      err.status = response.status;
      err.data = { detail };
      throw err;
    }

    return response.json();
  }

  /** Get file metadata (no content). */
  async getFileMetadata(fileId: string): Promise<FileResponse> {
    return this.fetch<FileResponse>(`${API_ENDPOINTS.files}/${fileId}`);
  }

  /** Build the URL for downloading/streaming file content. */
  getFileContentUrl(fileId: string): string {
    return `${this.baseUrl}${API_ENDPOINTS.files}/${fileId}/content`;
  }

  /**
   * Fetch file content as a Blob (with auth headers).
   * Useful for rendering images/audio in the browser.
   */
  async getFileContent(fileId: string): Promise<Blob> {
    const url = this.getFileContentUrl(fileId);
    const headers: Record<string, string> = {};
    if (this.sessionToken) {
      headers['Authorization'] = `Bearer ${this.sessionToken}`;
    }

    const response = await fetch(url, {
      headers,
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch file content (${response.status})`);
    }

    return response.blob();
  }

  /** Soft-delete a file. */
  async deleteFile(fileId: string): Promise<FileResponse> {
    return this.fetch<FileResponse>(`${API_ENDPOINTS.files}/${fileId}`, {
      method: 'DELETE',
    });
  }

  /** List all files attached to a test. */
  async getTestFiles(testId: string): Promise<FileResponse[]> {
    return this.fetch<FileResponse[]>(
      `${API_ENDPOINTS.tests}/${testId}/files`
    );
  }
}
