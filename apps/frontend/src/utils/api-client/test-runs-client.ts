import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { 
  TestRun, 
  TestRunCreate, 
  TestRunUpdate, 
  TestRunDetail
} from './interfaces/test-run';
import { Behavior } from './interfaces/behavior';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';

type TestRunsQueryParams = Partial<PaginationParams> & {
  test_configuration_id?: string;
  filter?: string;
};

const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50,
  sort_by: 'created_at',
  sort_order: 'desc'
};

export class TestRunsClient extends BaseApiClient {
  async getTestRuns(params: TestRunsQueryParams = {}): Promise<PaginatedResponse<TestRunDetail>> {
    const { test_configuration_id, filter, ...paginationParams } = params;
    
    const queryParams = new URLSearchParams();
    if (test_configuration_id) queryParams.append('test_configuration_id', test_configuration_id);
    if (filter) queryParams.append('$filter', filter);
    
    const endpoint = queryParams.toString() 
      ? `${API_ENDPOINTS.testRuns}?${queryParams.toString()}`
      : API_ENDPOINTS.testRuns;

    return this.fetchPaginated<TestRunDetail>(
      endpoint,
      { ...DEFAULT_PAGINATION, ...paginationParams },
      { cache: 'no-store' }
    );
  }

  // For backwards compatibility with components using the separate count endpoint
  async getTestRunsCount(): Promise<number> {
    const response = await this.getTestRuns({
      skip: 0,
      limit: 1
    });
    return response.pagination.totalCount;
  }

  async getTestRun(id: string): Promise<TestRunDetail> {
    return this.fetch<TestRunDetail>(`${API_ENDPOINTS.testRuns}/${id}`);
  }

  async getTestRunBehaviors(testRunId: string): Promise<Behavior[]> {
    return this.fetch<Behavior[]>(`${API_ENDPOINTS.testRuns}/${testRunId}/behaviors`);
  }

  async createTestRun(testRun: TestRunCreate): Promise<TestRun> {
    return this.fetch<TestRun>(API_ENDPOINTS.testRuns, {
      method: 'POST',
      body: JSON.stringify(testRun),
    });
  }

  async updateTestRun(id: string, data: TestRunUpdate): Promise<TestRun> {
    return this.fetch<TestRun>(`${API_ENDPOINTS.testRuns}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteTestRun(id: string): Promise<void> {
    return this.fetch(`${API_ENDPOINTS.testRuns}/${id}`, {
      method: 'DELETE',
    });
  }

  async getTestRunsByTestConfiguration(testConfigurationId: string, params: Partial<PaginationParams> = {}): Promise<PaginatedResponse<TestRunDetail>> {
    return this.getTestRuns({
      ...DEFAULT_PAGINATION,
      ...params,
      test_configuration_id: testConfigurationId
    });
  }
} 