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
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    if (description) formData.append('description', description);

    return this.fetch<Source>(`${API_ENDPOINTS.sources}/upload/`, {
      method: 'POST',
      body: formData,
      headers: {
        // Don't set Content-Type, let browser set it with boundary for multipart/form-data
      },
    });
  }
}
