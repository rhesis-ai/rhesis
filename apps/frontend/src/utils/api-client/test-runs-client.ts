import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  TestRun,
  TestRunCreate,
  TestRunUpdate,
  TestRunDetail,
} from './interfaces/test-run';
import {
  TestRunStatsResponse,
  TestRunStatsParams,
} from './interfaces/test-run-stats';
import { Behavior } from './interfaces/behavior';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';
import { joinUrl } from '@/utils/url';

type TestRunsQueryParams = Partial<PaginationParams> & {
  test_configuration_id?: string;
  filter?: string;
};

const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50,
  sort_by: 'created_at',
  sort_order: 'desc',
};

export class TestRunsClient extends BaseApiClient {
  async getTestRuns(
    params: TestRunsQueryParams = {}
  ): Promise<PaginatedResponse<TestRunDetail>> {
    const { test_configuration_id, filter, ...paginationParams } = params;

    // Build the OData filter
    let finalFilter = filter;
    if (test_configuration_id) {
      const configFilter = `test_configuration/id eq '${test_configuration_id}'`;
      finalFilter = filter ? `(${filter}) and (${configFilter})` : configFilter;
    }

    // Prepare parameters for fetchPaginated
    const fetchParams: PaginationParams & { $filter?: string } = {
      ...DEFAULT_PAGINATION,
      ...paginationParams,
    };

    if (finalFilter) {
      fetchParams.$filter = finalFilter;
    }

    return this.fetchPaginated<TestRunDetail>(
      API_ENDPOINTS.testRuns,
      fetchParams as PaginationParams & { $filter?: string } & Record<string, unknown>,
      { cache: 'no-store' }
    );
  }

  // For backwards compatibility with components using the separate count endpoint
  async getTestRunsCount(): Promise<number> {
    const response = await this.getTestRuns({
      skip: 0,
      limit: 1,
    });
    return response.pagination.totalCount;
  }

  async getTestRun(id: string): Promise<TestRunDetail> {
    return this.fetch<TestRunDetail>(`${API_ENDPOINTS.testRuns}/${id}`);
  }

  async getTestRunBehaviors(testRunId: string): Promise<Behavior[]> {
    return this.fetch<Behavior[]>(
      `${API_ENDPOINTS.testRuns}/${testRunId}/behaviors`
    );
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

  async getTestRunsByTestConfiguration(
    testConfigurationId: string,
    params: Partial<PaginationParams> = {}
  ): Promise<PaginatedResponse<TestRunDetail>> {
    return this.getTestRuns({
      ...DEFAULT_PAGINATION,
      ...params,
      test_configuration_id: testConfigurationId,
    });
  }

  async downloadTestRun(testRunId: string): Promise<Blob> {
    return this.fetchBlob(`${API_ENDPOINTS.testRuns}/${testRunId}/download`);
  }

  async getTestRunStats(
    params: TestRunStatsParams = {}
  ): Promise<TestRunStatsResponse> {
    const queryParams = new URLSearchParams();

    // Add all parameters to query string
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          // Handle array parameters (e.g., test_run_ids, user_ids)
          value.forEach(item => queryParams.append(key, String(item)));
        } else {
          queryParams.append(key, String(value));
        }
      }
    });

    const url = `${API_ENDPOINTS.testRuns}/stats${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
    return this.fetch<TestRunStatsResponse>(url);
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
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API error: ${response.status} - ${errorText}`);
    }

    return response.blob();
  }
}
