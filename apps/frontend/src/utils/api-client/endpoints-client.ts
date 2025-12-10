import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { Endpoint, EndpointTestRequest } from './interfaces/endpoint';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';

// Default pagination settings
const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 10,
  sort_by: 'created_at',
  sort_order: 'desc',
};

export type EndpointCreate = Omit<Endpoint, 'id'>;

export class EndpointsClient extends BaseApiClient {
  async getEndpoints(
    params: Partial<PaginationParams> = {}
  ): Promise<PaginatedResponse<Endpoint>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };

    return this.fetchPaginated<Endpoint>(
      API_ENDPOINTS.endpoints,
      paginationParams,
      { cache: 'no-store' }
    );
  }

  async getEndpoint(identifier: string): Promise<Endpoint> {
    return this.fetch<Endpoint>(`${API_ENDPOINTS.endpoints}/${identifier}`);
  }

  async createEndpoint(endpoint: EndpointCreate): Promise<Endpoint> {
    try {
      return await this.fetch<Endpoint>(API_ENDPOINTS.endpoints, {
        method: 'POST',
        body: JSON.stringify(endpoint),
      });
    } catch (error) {
      throw error;
    }
  }

  async updateEndpoint(id: string, data: Partial<Endpoint>): Promise<Endpoint> {
    return this.fetch<Endpoint>(`${API_ENDPOINTS.endpoints}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteEndpoint(id: string): Promise<void> {
    return this.fetch(`${API_ENDPOINTS.endpoints}/${id}`, {
      method: 'DELETE',
    });
  }

  async invokeEndpoint(id: string, inputData: any): Promise<any> {
    return this.fetch<any>(`${API_ENDPOINTS.endpoints}/${id}/invoke`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(inputData),
    });
  }

  async testEndpoint(testConfig: EndpointTestRequest): Promise<any> {
    return this.fetch<any>(`${API_ENDPOINTS.endpoints}/test`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(testConfig),
    });
  }

  async executeTestSet(endpointId: string, testSetId: string): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}/endpoints/${endpointId}/test-sets/${testSetId}/execute`,
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.sessionToken}`,
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      throw new Error('Failed to execute test set');
    }

    return response.json();
  }

  async executeEndpoint(id: string, test_set_ids: string[]): Promise<any> {
    return this.fetch<any>(`${API_ENDPOINTS.endpoints}/${id}/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ test_set_ids }),
    });
  }
}
