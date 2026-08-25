import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  TestRun,
  TestRunCreate,
  TestRunUpdate,
  TestRunDetail,
  TestRunBulkDeleteResponse,
} from './interfaces/test-run';
import { Requirement } from './interfaces/requirement';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';
import { joinUrl } from '@/utils/url';

type TestRunsQueryParams = Partial<PaginationParams> & {
  test_configuration_id?: string;
  filter?: string;
  has_experiment?: boolean;
  has_reviews?: boolean;
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
    const {
      test_configuration_id,
      filter,
      has_experiment,
      has_reviews,
      ...paginationParams
    } = params;

    // Build the OData filter
    let finalFilter = filter;
    if (test_configuration_id) {
      const configFilter = `test_configuration/id eq '${test_configuration_id}'`;
      finalFilter = filter ? `(${filter}) and (${configFilter})` : configFilter;
    }

    // Prepare parameters for fetchPaginated
    const fetchParams: PaginationParams & {
      $filter?: string;
      has_experiment?: boolean;
      has_reviews?: boolean;
    } = {
      ...DEFAULT_PAGINATION,
      ...paginationParams,
    };

    if (finalFilter) {
      fetchParams.$filter = finalFilter;
    }

    if (has_experiment !== undefined) {
      fetchParams.has_experiment = has_experiment;
    }

    if (has_reviews !== undefined) {
      fetchParams.has_reviews = has_reviews;
    }

    return this.fetchPaginated<TestRunDetail>(
      API_ENDPOINTS.testRuns,
      fetchParams as PaginationParams & Record<string, unknown>,
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

  async getTestRunRequirements(testRunId: string): Promise<Requirement[]> {
    return this.fetch<Requirement[]>(
      `${API_ENDPOINTS.testRuns}/${testRunId}${API_ENDPOINTS.requirements}`
    );
  }

  async getTestRunMetrics(testRunId: string): Promise<string[]> {
    return this.fetch<string[]>(
      `${API_ENDPOINTS.testRuns}/${testRunId}/metrics`
    );
  }

  async createTestRun(testRun: TestRunCreate): Promise<TestRun> {
    return this.fetch<TestRun>(`${API_ENDPOINTS.testRuns}/`, {
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

  async bulkDeleteTestRuns(
    testRunIds: string[]
  ): Promise<TestRunBulkDeleteResponse> {
    return this.bulkDelete<TestRunBulkDeleteResponse>(
      API_ENDPOINTS.testRuns,
      'test_run_ids',
      testRunIds
    );
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

  async cancelTestRun(id: string): Promise<TestRun> {
    return this.fetch<TestRun>(`${API_ENDPOINTS.testRuns}/${id}/cancel`, {
      method: 'POST',
    });
  }

  async downloadTestRun(testRunId: string): Promise<Blob> {
    return this.fetchBlob(`${API_ENDPOINTS.testRuns}/${testRunId}/download`);
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
