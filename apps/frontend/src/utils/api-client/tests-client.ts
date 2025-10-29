import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Test,
  TestCreate,
  TestUpdate,
  TestDetail,
  TestStats,
  TestBulkCreateRequest,
  TestBulkCreateResponse,
  PriorityLevel,
} from './interfaces/tests';
import { StatsOptions } from './interfaces/common';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';
import {
  IndividualTestStats,
  IndividualTestStatsOptions,
} from './interfaces/individual-test-stats';

// Default pagination settings
const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50,
  sort_by: 'created_at',
  sort_order: 'desc',
};

export interface TestsResponse {
  tests: TestDetail[];
  totalCount: number;
}

export class TestsClient extends BaseApiClient {
  // Priority translation functions
  private numericToPriorityString(
    priorityNum: number | undefined
  ): PriorityLevel {
    switch (priorityNum) {
      case 0:
        return 'Low';
      case 2:
        return 'High';
      case 3:
        return 'Urgent';
      case 1:
      default:
        return 'Medium';
    }
  }

  private priorityStringToNumeric(priority: PriorityLevel | undefined): number {
    switch (priority) {
      case 'Low':
        return 0;
      case 'High':
        return 2;
      case 'Urgent':
        return 3;
      case 'Medium':
      default:
        return 1;
    }
  }

  // Convert test object's numeric priority to string priority
  private convertTestPriority(test: TestDetail): TestDetail {
    const result = { ...test };
    if (result.priority !== undefined) {
      // @ts-ignore - We're adding a string priority property
      result.priorityLevel = this.numericToPriorityString(result.priority);
    }
    return result;
  }

  async getTests(
    params?: PaginationParams & { filter?: string }
  ): Promise<PaginatedResponse<TestDetail>> {
    const { filter, ...paginationParams } = params || {};
    const finalParams = { ...DEFAULT_PAGINATION, ...paginationParams };

    const response = await this.fetchPaginated<TestDetail>(
      API_ENDPOINTS.tests,
      {
        ...finalParams,
        ...(filter && { $filter: filter }),
      },
      {
        cache: 'no-store',
      }
    );

    // Convert numeric priorities to string values
    return {
      ...response,
      data: response.data.map(test => this.convertTestPriority(test)),
    };
  }

  async getTest(id: string): Promise<TestDetail> {
    const test = await this.fetch<TestDetail>(`${API_ENDPOINTS.tests}/${id}`);

    // Convert numeric priority to string value
    return this.convertTestPriority(test);
  }

  async createTest(test: TestCreate): Promise<Test> {
    // Handle priority conversion if a string priority is provided
    const apiTest = { ...test };

    // @ts-ignore - Check if priorityLevel exists and convert it
    if (apiTest.priorityLevel) {
      // @ts-ignore - Convert priorityLevel to numeric priority
      apiTest.priority = this.priorityStringToNumeric(apiTest.priorityLevel);
      // @ts-ignore - Remove priorityLevel as it's not expected by the API
      delete apiTest.priorityLevel;
    }

    return this.fetch<Test>(API_ENDPOINTS.tests, {
      method: 'POST',
      body: JSON.stringify(apiTest),
    });
  }

  async updateTest(id: string, test: TestUpdate): Promise<Test> {
    // Handle priority conversion if a string priority is provided
    const apiTest = { ...test };

    // @ts-ignore - Check if priorityLevel exists and convert it
    if (apiTest.priorityLevel) {
      // @ts-ignore - Convert priorityLevel to numeric priority
      apiTest.priority = this.priorityStringToNumeric(apiTest.priorityLevel);
      // @ts-ignore - Remove priorityLevel as it's not expected by the API
      delete apiTest.priorityLevel;
    }

    return this.fetch<Test>(`${API_ENDPOINTS.tests}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(apiTest),
    });
  }

  async deleteTest(id: string): Promise<Test> {
    return this.fetch<Test>(`${API_ENDPOINTS.tests}/${id}`, {
      method: 'DELETE',
    });
  }

  async getTestStats(options: StatsOptions = {}): Promise<TestStats> {
    const queryParams = new URLSearchParams();
    if (options.top !== undefined)
      queryParams.append('top', options.top.toString());
    if (options.months !== undefined)
      queryParams.append('months', options.months.toString());
    if (options.mode !== undefined) queryParams.append('mode', options.mode);

    const queryString = queryParams.toString();
    const url = queryString
      ? `${API_ENDPOINTS.tests}/stats?${queryString}`
      : `${API_ENDPOINTS.tests}/stats`;

    return this.fetch<TestStats>(url, {
      cache: 'no-store',
    });
  }

  async createTestsBulk(
    request: TestBulkCreateRequest
  ): Promise<TestBulkCreateResponse> {
    return this.fetch<TestBulkCreateResponse>(`${API_ENDPOINTS.tests}/bulk`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getIndividualTestStats(
    testId: string,
    options: IndividualTestStatsOptions = {}
  ): Promise<IndividualTestStats> {
    const queryParams = new URLSearchParams();
    if (options.recent_runs_limit !== undefined)
      queryParams.append(
        'recent_runs_limit',
        options.recent_runs_limit.toString()
      );
    if (options.months !== undefined)
      queryParams.append('months', options.months.toString());
    if (options.start_date !== undefined)
      queryParams.append('start_date', options.start_date);
    if (options.end_date !== undefined)
      queryParams.append('end_date', options.end_date);

    const queryString = queryParams.toString();
    const url = queryString
      ? `${API_ENDPOINTS.tests}/${testId}/stats?${queryString}`
      : `${API_ENDPOINTS.tests}/${testId}/stats`;

    return this.fetch<IndividualTestStats>(url, {
      cache: 'no-store',
    });
  }
}
