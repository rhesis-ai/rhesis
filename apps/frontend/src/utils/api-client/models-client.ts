import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Model,
  ModelCreate,
  ModelUpdate,
  ModelDetail,
  ModelQueryParams,
  TestModelConnectionRequest,
  TestModelConnectionResponse,
} from './interfaces/model';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';
import { UUID } from 'crypto';

// Default pagination settings
const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50,
  sort_by: 'created_at',
  sort_order: 'desc',
};

export class ModelsClient extends BaseApiClient {
  async getModels(
    params?: ModelQueryParams
  ): Promise<PaginatedResponse<ModelDetail>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };

    return this.fetchPaginated<ModelDetail>(
      API_ENDPOINTS.models,
      paginationParams,
      {
        cache: 'no-store',
      }
    );
  }

  async getModel(id: UUID): Promise<ModelDetail> {
    return this.fetch<ModelDetail>(`${API_ENDPOINTS.models}/${id}`);
  }

  async createModel(model: ModelCreate): Promise<Model> {
    return this.fetch<Model>(API_ENDPOINTS.models, {
      method: 'POST',
      body: JSON.stringify(model),
    });
  }

  async updateModel(id: UUID, model: ModelUpdate): Promise<Model> {
    return this.fetch<Model>(`${API_ENDPOINTS.models}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(model),
    });
  }

  async deleteModel(id: UUID): Promise<void> {
    return this.fetch<void>(`${API_ENDPOINTS.models}/${id}`, {
      method: 'DELETE',
    });
  }

  async testModelConnection(
    id: UUID
  ): Promise<{ status: string; message: string }> {
    return this.fetch<{ status: string; message: string }>(
      `${API_ENDPOINTS.models}/${id}/test`,
      {
        method: 'POST',
      }
    );
  }

  async testConnection(
    request: TestModelConnectionRequest
  ): Promise<TestModelConnectionResponse> {
    return this.fetch<TestModelConnectionResponse>(
      `${API_ENDPOINTS.models}/test-connection`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );
  }

  async getProviderModels(provider: string): Promise<string[]> {
    return this.fetch<string[]>(`${API_ENDPOINTS.models}/provider/${provider}`);
  }

  async getProviderEmbeddingModels(provider: string): Promise<string[]> {
    return this.fetch<string[]>(
      `${API_ENDPOINTS.models}/provider/${provider}/embeddings`
    );
  }
}
