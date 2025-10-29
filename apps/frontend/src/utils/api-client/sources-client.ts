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
      let errorData: any;
      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          errorData = await response.json();
          if (errorData.detail) {
            errorMessage = Array.isArray(errorData.detail)
              ? errorData.detail
                  .map(
                    (err: any) => `${err.loc?.join('.') || 'field'}: ${err.msg}`
                  )
                  .join(', ')
              : errorData.detail;
          } else if (errorData.message) {
            errorMessage = errorData.message;
          } else {
            errorMessage = JSON.stringify(errorData, null, 2);
          }
        } else {
          errorMessage = await response.text();
        }
      } catch (parseError) {
        errorMessage = await response.text();
      }

      const error = new Error(
        `API error: ${response.status} - ${errorMessage}`
      ) as Error & {
        status?: number;
        data?: any;
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
      let errorData: any;

      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          errorData = await response.json();
          if (errorData.detail) {
            errorMessage = Array.isArray(errorData.detail)
              ? errorData.detail
                  .map(
                    (err: any) => `${err.loc?.join('.') || 'field'}: ${err.msg}`
                  )
                  .join(', ')
              : errorData.detail;
          } else if (errorData.message) {
            errorMessage = errorData.message;
          } else {
            errorMessage = JSON.stringify(errorData, null, 2);
          }
        } else {
          errorMessage = await response.text();
        }
      } catch (parseError) {
        errorMessage = await response.text();
      }

      const error = new Error(
        `API error: ${response.status} - ${errorMessage}`
      ) as Error & {
        status?: number;
        data?: any;
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
      let errorData: any;

      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          errorData = await response.json();
          if (errorData.detail) {
            errorMessage = Array.isArray(errorData.detail)
              ? errorData.detail
                  .map(
                    (err: any) => `${err.loc?.join('.') || 'field'}: ${err.msg}`
                  )
                  .join(', ')
              : errorData.detail;
          } else if (errorData.message) {
            errorMessage = errorData.message;
          } else {
            errorMessage = JSON.stringify(errorData, null, 2);
          }
        } else {
          errorMessage = await response.text();
        }
      } catch (parseError) {
        errorMessage = await response.text();
      }

      const error = new Error(
        `API error: ${response.status} - ${errorMessage}`
      ) as Error & {
        status?: number;
        data?: any;
      };
      error.status = response.status;
      error.data = errorData;
      throw error;
    }

    return response.blob();
  }

  async extractSourceContent(
    id: UUID
  ): Promise<{ content: string; metadata: any }> {
    return this.fetch<{ content: string; metadata: any }>(
      `${API_ENDPOINTS.sources}/${id}/extract`,
      {
        method: 'POST',
      }
    );
  }
}
