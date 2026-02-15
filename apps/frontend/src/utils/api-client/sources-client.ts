import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Source,
  SourceCreate,
  SourceUpdate,
  SourcesQueryParams,
} from './interfaces/source';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';
import { UUID } from 'crypto';
import { joinUrl } from '../url';

/** Validation error detail shape from API error responses */
interface ValidationErrorDetail {
  loc?: (string | number)[];
  msg: string;
  type?: string;
}

/** Extract human-readable message from API error response data */
function getErrorMessageFromErrorData(errorData: unknown): string {
  if (typeof errorData !== 'object' || errorData === null) {
    return String(errorData);
  }
  const data = errorData as Record<string, unknown>;
  if (data.detail !== undefined) {
    if (Array.isArray(data.detail)) {
      return data.detail
        .map(
          (err: unknown) =>
            `${(err as ValidationErrorDetail).loc?.join('.') || 'field'}: ${(err as ValidationErrorDetail).msg}`
        )
        .join(', ');
    }
    return String(data.detail);
  }
  if (data.message !== undefined) {
    return String(data.message);
  }
  return JSON.stringify(errorData, null, 2);
}

// Default pagination settings
const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50,
  sort_by: 'created_at',
  sort_order: 'desc',
};

export class SourcesClient extends BaseApiClient {
  async getSources(
    params?: SourcesQueryParams
  ): Promise<PaginatedResponse<Source>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };

    return this.fetchPaginated<Source>(
      API_ENDPOINTS.sources,
      paginationParams,
      {
        cache: 'no-store',
      }
    );
  }

  async getSource(id: UUID): Promise<Source> {
    return this.fetch<Source>(`${API_ENDPOINTS.sources}/${id}`);
  }

  async getSourceWithContent(id: UUID): Promise<Source> {
    return this.fetch<Source>(`${API_ENDPOINTS.sources}/${id}/content`);
  }

  async createSource(source: SourceCreate): Promise<Source> {
    return this.fetch<Source>(API_ENDPOINTS.sources, {
      method: 'POST',
      body: JSON.stringify(source),
    });
  }

  /**
   * Create a source from text content (not file upload)
   * @param title - Title of the source
   * @param content - Text content of the source
   * @param description - Optional description
   * @param metadata - Optional metadata (e.g., MCP server info, URL)
   * @param source_type_id - Optional source type ID
   * @returns Created source
   */
  async createSourceFromContent(
    title: string,
    content: string,
    description?: string,
    metadata?: Record<string, unknown>,
    source_type_id?: UUID
  ): Promise<Source> {
    const sourceData: SourceCreate = {
      title,
      content,
      description,
      source_metadata: metadata,
      source_type_id,
    };

    return this.createSource(sourceData);
  }

  async updateSource(id: UUID, source: SourceUpdate): Promise<Source> {
    return this.fetch<Source>(`${API_ENDPOINTS.sources}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(source),
    });
  }

  async deleteSource(id: UUID): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.sources}/${id}`, {
      method: 'DELETE',
    });
  }

  async uploadSource(
    file: File,
    title?: string,
    description?: string
  ): Promise<Source> {
    // Use direct URL construction to preserve trailing slash
    const url = new URL(`${this.baseUrl}/sources/upload`);

    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    if (description) formData.append('description', description);

    // For multipart/form-data, we need to override the default headers
    // Create headers object without Content-Type so browser can set it correctly
    const headers: Record<string, string> = {};

    // Add authorization if we have a session token (copied from BaseApiClient logic)
    if (this.sessionToken) {
      headers['Authorization'] = `Bearer ${this.sessionToken}`;
    }

    // Use direct fetch to avoid BaseApiClient's default Content-Type header
    const response = await fetch(url.toString(), {
      method: 'POST',
      body: formData,
      headers,
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = '';
      let errorData: unknown;
      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          errorData = await response.json();
          errorMessage = getErrorMessageFromErrorData(errorData);
        } else {
          errorMessage = await response.text();
        }
      } catch (_parseError) {
        errorMessage = await response.text();
      }

      const error = new Error(
        `API error: ${response.status} - ${errorMessage}`
      ) as Error & {
        status?: number;
        data?: unknown;
      };
      error.status = response.status;
      error.data = errorData;

      // Handle authentication errors
      if (response.status === 401 || response.status === 403) {
        throw new Error('Unauthorized');
      }

      throw error;
    }

    return response.json();
  }

  async getSourceContent(id: UUID): Promise<string> {
    return this.fetchText(`${API_ENDPOINTS.sources}/${id}/file`);
  }

  async getSourceContentBlob(id: UUID): Promise<Blob> {
    return this.fetchBlob(`${API_ENDPOINTS.sources}/${id}/file`);
  }

  protected async fetchText(
    endpoint: keyof typeof API_ENDPOINTS | string,
    options: RequestInit = {}
  ): Promise<string> {
    const path =
      API_ENDPOINTS[endpoint as keyof typeof API_ENDPOINTS] || endpoint;
    const url = joinUrl(this.baseUrl, path);
    const headers = this.getHeaders();

    const response = await fetch(url, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = '';
      let errorData: unknown;

      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          errorData = await response.json();
          errorMessage = getErrorMessageFromErrorData(errorData);
        } else {
          errorMessage = await response.text();
        }
      } catch (_parseError) {
        errorMessage = await response.text();
      }

      const error = new Error(
        `API error: ${response.status} - ${errorMessage}`
      ) as Error & {
        status?: number;
        data?: unknown;
      };
      error.status = response.status;
      error.data = errorData;
      throw error;
    }

    return response.text();
  }

  protected async fetchBlob(
    endpoint: keyof typeof API_ENDPOINTS | string,
    options: RequestInit = {}
  ): Promise<Blob> {
    const path =
      API_ENDPOINTS[endpoint as keyof typeof API_ENDPOINTS] || endpoint;
    const url = joinUrl(this.baseUrl, path);
    const headers = this.getHeaders();

    const response = await fetch(url, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = '';
      let errorData: unknown;

      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          errorData = await response.json();
          errorMessage = getErrorMessageFromErrorData(errorData);
        } else {
          errorMessage = await response.text();
        }
      } catch (_parseError) {
        errorMessage = await response.text();
      }

      const error = new Error(
        `API error: ${response.status} - ${errorMessage}`
      ) as Error & {
        status?: number;
        data?: unknown;
      };
      error.status = response.status;
      error.data = errorData;
      throw error;
    }

    return response.blob();
  }

  async extractSourceContent(
    id: UUID
  ): Promise<{ content: string; metadata: Record<string, unknown> }> {
    return this.fetch<{ content: string; metadata: Record<string, unknown> }>(
      `${API_ENDPOINTS.sources}/${id}/extract`,
      {
        method: 'POST',
      }
    );
  }
}
