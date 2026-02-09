import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  TestConfiguration,
  TestConfigurationCreate,
  TestConfigurationUpdate,
  TestConfigurationDetail,
  TestConfigurationExecuteResponse,
} from './interfaces/test-configuration';
import { TestRunDetail } from './interfaces/test-run';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';

// Default pagination settings
const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 10,
  sort_by: 'created_at',
  sort_order: 'desc',
};

export class TestConfigurationsClient extends BaseApiClient {
  async getTestConfigurations(
    params: Partial<PaginationParams> = {}
  ): Promise<PaginatedResponse<TestConfigurationDetail>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };

    return this.fetchPaginated<TestConfigurationDetail>(
      API_ENDPOINTS.testConfigurations,
      paginationParams,
      {
        cache: 'no-store',
      }
    );
  }

  // For backwards compatibility
  async getTestConfigurationsCount(): Promise<number> {
    const response = await this.getTestConfigurations({
      skip: 0,
      limit: 1,
    });
    return response.pagination.totalCount;
  }

  async getTestConfiguration(id: string): Promise<TestConfigurationDetail> {
    return this.fetch<TestConfigurationDetail>(
      `${API_ENDPOINTS.testConfigurations}/${id}`
    );
  }

  async createTestConfiguration(
    testConfiguration: TestConfigurationCreate
  ): Promise<TestConfiguration> {
    return this.fetch<TestConfiguration>(API_ENDPOINTS.testConfigurations, {
      method: 'POST',
      body: JSON.stringify(testConfiguration),
    });
  }

  async updateTestConfiguration(
    id: string,
    testConfiguration: TestConfigurationUpdate
  ): Promise<TestConfiguration> {
    return this.fetch<TestConfiguration>(
      `${API_ENDPOINTS.testConfigurations}/${id}`,
      {
        method: 'PUT',
        body: JSON.stringify(testConfiguration),
      }
    );
  }

  async deleteTestConfiguration(id: string): Promise<TestConfiguration> {
    return this.fetch<TestConfiguration>(
      `${API_ENDPOINTS.testConfigurations}/${id}`,
      {
        method: 'DELETE',
      }
    );
  }

  async executeTestConfiguration(
    id: string
  ): Promise<TestConfigurationExecuteResponse> {
    return this.fetch<TestConfigurationExecuteResponse>(
      `${API_ENDPOINTS.testConfigurations}/${id}/execute`,
      {
        method: 'POST',
      }
    );
  }

  async getTestRunsByTestConfiguration(
    id: string,
    params: Partial<PaginationParams> = {}
  ): Promise<PaginatedResponse<TestRunDetail>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };

    return this.fetchPaginated<TestRunDetail>(
      `${API_ENDPOINTS.testConfigurations}/${id}/test_runs`,
      paginationParams,
      {
        cache: 'no-store',
      }
    );
  }

  async getLatestTestRun(id: string): Promise<TestRunDetail | null> {
    const response = await this.getTestRunsByTestConfiguration(id, {
      limit: 1,
    });
    return response.data.length > 0
      ? this.fetch<TestRunDetail>(
          `${API_ENDPOINTS.testRuns}/${response.data[0].id}`
        )
      : null;
  }
}
