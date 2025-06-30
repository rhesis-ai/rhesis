import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  TestResult,
  TestResultCreate,
  TestResultUpdate,
  TestResultDetail,
  TestResultStats
} from './interfaces/test-results';
import { StatsOptions } from './interfaces/common';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';

const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50,
  sort_by: 'created_at',
  sort_order: 'desc'
};

export class TestResultsClient extends BaseApiClient {
  async getTestResults(params: Partial<PaginationParams> & { filter?: string } = {}): Promise<PaginatedResponse<TestResultDetail>> {
    const { filter, ...paginationParams } = params;
    
    return this.fetchPaginated<TestResultDetail>(
      API_ENDPOINTS.testResults,
      { 
        ...DEFAULT_PAGINATION, 
        ...paginationParams,
        $filter: filter
      },
      { cache: 'no-store' }
    );
  }

  // For backwards compatibility
  async getTestResultsCount(): Promise<number> {
    const response = await this.getTestResults({ 
      skip: 0,
      limit: 1
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

  async updateTestResult(id: string, testResult: TestResultUpdate): Promise<TestResult> {
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

  async getTestResultStats(options: StatsOptions = {}): Promise<TestResultStats> {
    const queryParams = new URLSearchParams();
    if (options.top !== undefined) queryParams.append('top', options.top.toString());
    if (options.months !== undefined) queryParams.append('months', options.months.toString());
    if (options.mode !== undefined) queryParams.append('mode', options.mode);

    const queryString = queryParams.toString();
    const url = queryString 
      ? `${API_ENDPOINTS.testResults}/stats?${queryString}` 
      : `${API_ENDPOINTS.testResults}/stats`;

    return this.fetch<TestResultStats>(url, {
      cache: 'no-store'
    });
  }
} 