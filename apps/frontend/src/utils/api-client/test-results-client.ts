import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  TestResult,
  TestResultCreate,
  TestResultUpdate,
  TestResultDetail,
  TestResultStats,
  TestResultsStats,
} from './interfaces/test-results';
import { StatsOptions, TestResultsStatsOptions } from './interfaces/common';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';

const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50,
  sort_by: 'created_at',
  sort_order: 'desc',
};

export class TestResultsClient extends BaseApiClient {
  async getTestResults(
    params: Partial<PaginationParams> & { filter?: string } = {}
  ): Promise<PaginatedResponse<TestResultDetail>> {
    const { filter, ...paginationParams } = params;

    return this.fetchPaginated<TestResultDetail>(
      API_ENDPOINTS.testResults,
      {
        ...DEFAULT_PAGINATION,
        ...paginationParams,
        $filter: filter,
      },
      { cache: 'no-store' }
    );
  }

  // For backwards compatibility
  async getTestResultsCount(): Promise<number> {
    const response = await this.getTestResults({
      skip: 0,
      limit: 1,
    });
    return response.pagination.totalCount;
  }

  async getTestResult(id: string): Promise<TestResultDetail> {
    return this.fetch<TestResultDetail>(`${API_ENDPOINTS.testResults}/${id}`);
  }

  async createTestResult(testResult: TestResultCreate): Promise<TestResult> {
    return this.fetch<TestResult>(API_ENDPOINTS.testResults, {
      method: 'POST',
      body: JSON.stringify(testResult),
    });
  }

  async updateTestResult(
    id: string,
    testResult: TestResultUpdate
  ): Promise<TestResult> {
    return this.fetch<TestResult>(`${API_ENDPOINTS.testResults}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(testResult),
    });
  }

  async deleteTestResult(id: string): Promise<TestResult> {
    return this.fetch<TestResult>(`${API_ENDPOINTS.testResults}/${id}`, {
      method: 'DELETE',
    });
  }

  // Legacy method for backward compatibility
  async getTestResultStats(
    options: StatsOptions = {}
  ): Promise<TestResultStats> {
    const queryParams = new URLSearchParams();
    if (options.top !== undefined)
      queryParams.append('top', options.top.toString());
    if (options.months !== undefined)
      queryParams.append('months', options.months.toString());
    if (options.mode !== undefined) queryParams.append('mode', options.mode);

    const queryString = queryParams.toString();
    const url = queryString
      ? `${API_ENDPOINTS.testResults}/stats?${queryString}`
      : `${API_ENDPOINTS.testResults}/stats`;

    return this.fetch<TestResultStats>(url, {
      cache: 'no-store',
    });
  }

  // Comprehensive stats method with full API support
  async getComprehensiveTestResultsStats(
    options: TestResultsStatsOptions = {}
  ): Promise<TestResultsStats> {
    const queryParams = new URLSearchParams();

    // Data mode
    if (options.mode !== undefined) queryParams.append('mode', options.mode);

    // Time range options
    if (options.months !== undefined)
      queryParams.append('months', options.months.toString());
    if (options.start_date !== undefined)
      queryParams.append('start_date', options.start_date);
    if (options.end_date !== undefined)
      queryParams.append('end_date', options.end_date);

    // Test-level filters (multiple values support)
    if (options.test_set_ids) {
      options.test_set_ids.forEach(id =>
        queryParams.append('test_set_ids', id)
      );
    }
    if (options.behavior_ids) {
      options.behavior_ids.forEach(id =>
        queryParams.append('behavior_ids', id)
      );
    }
    if (options.category_ids) {
      options.category_ids.forEach(id =>
        queryParams.append('category_ids', id)
      );
    }
    if (options.topic_ids) {
      options.topic_ids.forEach(id => queryParams.append('topic_ids', id));
    }
    if (options.status_ids) {
      options.status_ids.forEach(id => queryParams.append('status_ids', id));
    }
    if (options.test_ids) {
      options.test_ids.forEach(id => queryParams.append('test_ids', id));
    }
    if (options.test_type_ids) {
      options.test_type_ids.forEach(id =>
        queryParams.append('test_type_ids', id)
      );
    }

    // Test run filters
    if (options.test_run_id !== undefined)
      queryParams.append('test_run_id', options.test_run_id);
    if (options.test_run_ids) {
      options.test_run_ids.forEach(id =>
        queryParams.append('test_run_ids', id)
      );
    }

    // User-related filters
    if (options.user_ids) {
      options.user_ids.forEach(id => queryParams.append('user_ids', id));
    }
    if (options.assignee_ids) {
      options.assignee_ids.forEach(id =>
        queryParams.append('assignee_ids', id)
      );
    }
    if (options.owner_ids) {
      options.owner_ids.forEach(id => queryParams.append('owner_ids', id));
    }

    // Other filters
    if (options.prompt_ids) {
      options.prompt_ids.forEach(id => queryParams.append('prompt_ids', id));
    }
    if (options.priority_min !== undefined)
      queryParams.append('priority_min', options.priority_min.toString());
    if (options.priority_max !== undefined)
      queryParams.append('priority_max', options.priority_max.toString());
    if (options.tags) {
      options.tags.forEach(tag => queryParams.append('tags', tag));
    }

    const queryString = queryParams.toString();
    const url = queryString
      ? `${API_ENDPOINTS.testResults}/stats?${queryString}`
      : `${API_ENDPOINTS.testResults}/stats`;

    return this.fetch<TestResultsStats>(url, {
      cache: 'no-store',
    });
  }
}
