import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import {
  TestResult,
  TestResultCreate,
  TestResultUpdate,
  TestResultDetail,
} from './interfaces/test-results';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';

const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50,
  sort_by: 'created_at',
  sort_order: 'desc',
};

export class TestResultsClient extends BaseApiClient {
  async getTestResults(
    params: Partial<PaginationParams> & {
      filter?: string;
      /** Drop test_output.conversation_summary (the full multi-turn transcript)
       * from each result -- for a caller rendering a results grid rather than
       * a conversation view. */
      stripConversation?: boolean;
    } = {}
  ): Promise<PaginatedResponse<TestResultDetail>> {
    const { filter, stripConversation, ...paginationParams } = params;

    return this.fetchPaginated<TestResultDetail>(
      API_ENDPOINTS.testResults,
      {
        ...DEFAULT_PAGINATION,
        ...paginationParams,
        $filter: filter,
        ...(stripConversation ? { strip_conversation: true } : {}),
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
    return this.fetch<TestResult>(`${API_ENDPOINTS.testResults}/`, {
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
}
