import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  Test,
  TestCreate,
  TestUpdate,
  TestDetail,
  TestBulkCreateRequest,
  TestBulkCreateResponse,
  TestExecuteRequest,
  TestExecuteResponse,
  ConversationToTestRequest,
  ConversationTestExtractionResponse,
  TestFacets,
  PriorityLevel,
} from './interfaces/tests';
import { TestSet } from './interfaces/test-set';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';
import type { EvaluationContractStatus } from './interfaces/evaluation-contract';

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

  async getAllTests(
    params?: Omit<PaginationParams & { filter?: string }, 'skip' | 'limit'>
  ): Promise<TestDetail[]> {
    const pageSize = 100;
    const allData: TestDetail[] = [];
    let skip = 0;
    let totalCount = Infinity;

    while (skip < totalCount) {
      const response = await this.getTests({
        ...params,
        skip,
        limit: pageSize,
      });
      if (response.data.length === 0) break;
      allData.push(...response.data);
      totalCount = response.pagination.totalCount;
      skip += pageSize;
    }

    return allData;
  }

  async getTestFacets(testSetId?: string): Promise<TestFacets> {
    const params = new URLSearchParams();
    if (testSetId) params.append('test_set_id', testSetId);
    const qs = params.toString();
    const url = `${API_ENDPOINTS.tests}/facets${qs ? `?${qs}` : ''}`;
    return this.fetch<TestFacets>(url, { cache: 'no-store' });
  }

  async getTest(id: string): Promise<TestDetail> {
    const test = await this.fetch<TestDetail>(`${API_ENDPOINTS.tests}/${id}`);

    // Convert numeric priority to string value
    return this.convertTestPriority(test);
  }

  async createTest(test: TestCreate): Promise<Test> {
    // Handle priority conversion if a string priority is provided
    const apiTest = { ...test };

    // @ts-expect-error - Check if priorityLevel exists and convert it
    if (apiTest.priorityLevel) {
      // @ts-expect-error - Convert priorityLevel to numeric priority
      apiTest.priority = this.priorityStringToNumeric(apiTest.priorityLevel);
      // @ts-expect-error - Remove priorityLevel as it's not expected by the API
      delete apiTest.priorityLevel;
    }

    return this.fetch<Test>(`${API_ENDPOINTS.tests}/`, {
      method: 'POST',
      body: JSON.stringify(apiTest),
    });
  }

  async updateTest(id: string, test: TestUpdate): Promise<Test> {
    // Handle priority conversion if a string priority is provided
    const apiTest = { ...test };

    // @ts-expect-error - Check if priorityLevel exists and convert it
    if (apiTest.priorityLevel) {
      // @ts-expect-error - Convert priorityLevel to numeric priority
      apiTest.priority = this.priorityStringToNumeric(apiTest.priorityLevel);
      // @ts-expect-error - Remove priorityLevel as it's not expected by the API
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

  async bulkDeleteTests(testIds: string[]): Promise<void> {
    await this.bulkDelete<void>(API_ENDPOINTS.tests, 'test_ids', testIds);
  }

  async createTestsBulk(
    request: TestBulkCreateRequest
  ): Promise<TestBulkCreateResponse> {
    return this.fetch<TestBulkCreateResponse>(`${API_ENDPOINTS.tests}/bulk`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async executeTest(request: TestExecuteRequest): Promise<TestExecuteResponse> {
    return this.fetch<TestExecuteResponse>(`${API_ENDPOINTS.tests}/execute`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async extractTestFromConversation(
    request: ConversationToTestRequest
  ): Promise<ConversationTestExtractionResponse> {
    return this.fetch<ConversationTestExtractionResponse>(
      `${API_ENDPOINTS.tests}/extract-from-conversation`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );
  }

  /** Read how a test was interpreted for scoring. Never triggers an interpretation. */
  async getTestInterpretation(
    testId: string
  ): Promise<EvaluationContractStatus> {
    return this.fetch<EvaluationContractStatus>(
      `${API_ENDPOINTS.tests}/${testId}/interpretation`
    );
  }

  /**
   * Derive or refresh a test's interpretation. Costs an LLM call, so it is only invoked from an
   * explicit user action. Without `force` this is a no-op when the stored reading is current.
   */
  async interpretTest(
    testId: string,
    options: { force?: boolean } = {}
  ): Promise<EvaluationContractStatus> {
    const query = options.force ? '?force=true' : '';
    return this.fetch<EvaluationContractStatus>(
      `${API_ENDPOINTS.tests}/${testId}/interpretation${query}`,
      { method: 'POST' }
    );
  }

  async getLinkedTestSets(
    testId: string,
    params: PaginationParams = {
      skip: 0,
      limit: 50,
      sort_by: 'created_at',
      sort_order: 'desc',
    }
  ): Promise<PaginatedResponse<TestSet>> {
    return this.fetchPaginated<TestSet>(
      `${API_ENDPOINTS.tests}/${testId}/test_sets`,
      params as PaginationParams & Record<string, unknown>
    );
  }
}
