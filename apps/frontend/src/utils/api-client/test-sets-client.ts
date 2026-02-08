import { BaseApiClient } from './base-client';
import { API_ENDPOINTS } from './config';
import { joinUrl } from '@/utils/url';
import {
  TestSet,
  TestSetCreate,
  TestSetStatsResponse,
  TestSetDetailStatsResponse,
  StatsOptions,
  TestSetBulkCreate,
  TestSetBulkResponse,
  TestSetBulkAssociateRequest,
  TestSetBulkAssociateResponse,
  TestSetBulkDisassociateRequest,
  TestSetBulkDisassociateResponse,
  GenerateTestsRequest,
  GenerateTestSetResponse,
  TestSetMetric,
  // Legacy imports for backwards compatibility
  TestSetGenerationRequest,
  TestSetGenerationResponse,
} from './interfaces/test-set';
import { TestDetail, PriorityLevel } from './interfaces/tests';
import { StatusClient } from './status-client';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';

interface TestSetsQueryParams extends Partial<PaginationParams> {
  // Add any additional test-set specific query params here
  has_runs?: boolean;
  $filter?: string;
}

const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50, // Default limit for paginated views
  sort_by: 'created_at',
  sort_order: 'desc',
};

/**
 * Utility function to build query parameters
 */
function buildQueryParams(params: Record<string, any>): string {
  const queryParams = new URLSearchParams();

  // Add all non-undefined parameters to the query string
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      queryParams.append(key, value.toString());
    }
  });

  const queryString = queryParams.toString();
  return queryString ? `?${queryString}` : '';
}

export class TestSetsClient extends BaseApiClient {
  private statusClient: StatusClient;

  constructor(sessionToken: string) {
    super(sessionToken);
    this.statusClient = new StatusClient(sessionToken);
  }

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

  // Convert test set object's numeric priority to string priority
  private convertTestSetPriority(testSet: TestSet): TestSet {
    const result = { ...testSet };
    if (result.priority !== undefined) {
      // @ts-expect-error - We're adding a string priority property
      result.priorityLevel = this.numericToPriorityString(result.priority);
    }
    return result;
  }

  /**
   * Generate a test set using the unified generation API
   * @param request - Generation request with config, num_tests, sources, etc.
   * @returns Response with task_id for tracking async generation
   */
  async generateTestSet(
    request: GenerateTestsRequest
  ): Promise<GenerateTestSetResponse> {
    return this.fetch<GenerateTestSetResponse>(
      `${API_ENDPOINTS.testSets}/generate`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );
  }

  async getTestSets(
    params: TestSetsQueryParams = {}
  ): Promise<PaginatedResponse<TestSet>> {
    const { has_runs, $filter, ...paginationParams } = params;
    const finalParams = { ...DEFAULT_PAGINATION, ...paginationParams };

    let response: PaginatedResponse<TestSet>;

    if (has_runs !== undefined || $filter) {
      // Build URL manually when has_runs or $filter is specified
      const queryParams = new URLSearchParams();

      // Add pagination parameters
      if (finalParams.skip !== undefined)
        queryParams.append('skip', finalParams.skip.toString());
      if (finalParams.limit !== undefined)
        queryParams.append('limit', finalParams.limit.toString());
      if (finalParams.sort_by)
        queryParams.append('sort_by', finalParams.sort_by);
      if (finalParams.sort_order)
        queryParams.append('sort_order', finalParams.sort_order);

      // Add has_runs parameter if provided
      if (has_runs !== undefined) {
        queryParams.append('has_runs', has_runs.toString());
      }

      // Add $filter parameter if provided
      if ($filter) {
        queryParams.append('$filter', $filter);
      }

      const path = API_ENDPOINTS.testSets;
      const queryString = queryParams.toString();
      const url = joinUrl(
        this.baseUrl,
        queryString ? `${path}?${queryString}` : path
      );

      // Use fetch to get raw response and construct paginated response manually
      const rawResponse = await fetch(url, {
        ...{ cache: 'no-store' },
        headers: {
          ...this.getHeaders(),
        },
        credentials: 'include',
      });

      if (!rawResponse.ok) {
        let errorMessage = '';
        let errorData: any;

        try {
          const contentType = rawResponse.headers.get('content-type');
          if (contentType && contentType.includes('application/json')) {
            errorData = await rawResponse.json();
            errorMessage =
              errorData.detail ||
              errorData.message ||
              JSON.stringify(errorData);
          } else {
            errorMessage = await rawResponse.text();
          }
        } catch (parseError) {
          errorMessage = await rawResponse.text();
        }

        const error = new Error(
          `API error: ${rawResponse.status} - ${errorMessage}`
        ) as Error & {
          status?: number;
          data?: any;
        };
        error.status = rawResponse.status;
        error.data = errorData;

        // Handle authentication errors
        if (rawResponse.status === 401 || rawResponse.status === 403) {
          throw new Error('Unauthorized');
        }

        throw error;
      }

      const totalCount = this.extractTotalCount(rawResponse);
      const data = (await rawResponse.json()) as TestSet[];
      const pageSize = finalParams.limit ?? 10;
      const currentPage = Math.floor((finalParams.skip ?? 0) / pageSize);
      const totalPages = Math.ceil(totalCount / pageSize);

      response = {
        data,
        pagination: {
          totalCount,
          skip: finalParams.skip ?? 0,
          limit: finalParams.limit ?? pageSize,
          currentPage,
          pageSize,
          totalPages,
        },
      };
    } else {
      // Use standard fetchPaginated when has_runs is not specified
      response = await this.fetchPaginated<TestSet>(
        API_ENDPOINTS.testSets,
        finalParams,
        {
          cache: 'no-store',
        }
      );
    }

    // Convert numeric priorities to string values
    if (!response || !response.data) {
      throw new Error('Invalid response structure from test sets API');
    }

    return {
      ...response,
      data: response.data.map(testSet => this.convertTestSetPriority(testSet)),
    };
  }

  async getTestSet(identifier: string): Promise<TestSet> {
    const testSet = await this.fetch<TestSet>(
      `${API_ENDPOINTS.testSets}/${identifier}`
    );
    // Convert numeric priority to string value
    return this.convertTestSetPriority(testSet);
  }

  async getTestSetStats(
    options: StatsOptions = {}
  ): Promise<TestSetStatsResponse> {
    const { top, months, mode } = options;

    const queryString = buildQueryParams({
      top,
      months,
      mode,
    });

    const url = `${API_ENDPOINTS.testSets}/stats${queryString}`;

    return this.fetch<TestSetStatsResponse>(url, {
      cache: 'no-store',
    });
  }

  async getTestSetDetailStats(
    identifier: string,
    options: StatsOptions = {}
  ): Promise<TestSetDetailStatsResponse> {
    const { top, months, mode } = options;

    const queryString = buildQueryParams({
      top,
      months,
      mode,
    });

    const url = `${API_ENDPOINTS.testSets}/${identifier}/stats${queryString}`;

    return this.fetch<TestSetDetailStatsResponse>(url, {
      cache: 'no-store',
    });
  }

  async createTestSet(testSet: TestSetCreate): Promise<TestSet> {
    return this.fetch<TestSet>(API_ENDPOINTS.testSets, {
      method: 'POST',
      body: JSON.stringify(testSet),
    });
  }

  async updateTestSet(
    id: string,
    testSet: Partial<TestSetCreate>
  ): Promise<TestSet> {
    const updatedTestSet = await this.fetch<TestSet>(
      `${API_ENDPOINTS.testSets}/${id}`,
      {
        method: 'PUT',
        body: JSON.stringify(testSet),
      }
    );

    // Convert the response priority back to string
    return this.convertTestSetPriority(updatedTestSet);
  }

  async deleteTestSet(id: string): Promise<void> {
    return this.fetch(`${API_ENDPOINTS.testSets}/${id}`, {
      method: 'DELETE',
    });
  }

  async executeTestSet(
    testSetId: string,
    endpointId: string,
    testConfigurationAttributes?: {
      execution_mode?: string;
      metrics?: Array<{ id: string; name: string; scope?: string[] }>;
      [key: string]: any;
    }
  ): Promise<TestSet> {
    // Build request body with execution_options and metrics
    const requestBody: Record<string, any> = {};

    if (testConfigurationAttributes) {
      // Extract metrics if present (goes at top level)
      const { metrics, ...executionOptions } = testConfigurationAttributes;

      // Add execution_options if there are any
      if (Object.keys(executionOptions).length > 0) {
        requestBody.execution_options = executionOptions;
      }

      // Add metrics at top level if present
      if (metrics && metrics.length > 0) {
        requestBody.metrics = metrics;
      }
    }

    const hasBody = Object.keys(requestBody).length > 0;

    return this.fetch<TestSet>(
      `${API_ENDPOINTS.testSets}/${testSetId}/execute/${endpointId}`,
      {
        method: 'POST',
        body: hasBody ? JSON.stringify(requestBody) : undefined,
        headers: hasBody ? { 'Content-Type': 'application/json' } : undefined,
      }
    );
  }

  async createTestSetBulk(
    testSetData: TestSetBulkCreate
  ): Promise<TestSetBulkResponse> {
    return this.fetch<TestSetBulkResponse>(`${API_ENDPOINTS.testSets}/bulk`, {
      method: 'POST',
      body: JSON.stringify(testSetData),
    });
  }

  async associateTestsWithTestSet(
    testSetId: string,
    testIds: string[]
  ): Promise<TestSetBulkAssociateResponse> {
    const request: TestSetBulkAssociateRequest = {
      test_ids: testIds as any[], // Type conversion from string[] to UUID[]
    };

    return this.fetch<TestSetBulkAssociateResponse>(
      `${API_ENDPOINTS.testSets}/${testSetId}/associate`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );
  }

  async disassociateTestsFromTestSet(
    testSetId: string,
    testIds: string[]
  ): Promise<TestSetBulkDisassociateResponse> {
    const request: TestSetBulkDisassociateRequest = {
      test_ids: testIds as any[], // Type conversion from string[] to UUID[]
    };

    return this.fetch<TestSetBulkDisassociateResponse>(
      `${API_ENDPOINTS.testSets}/${testSetId}/disassociate`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );
  }

  async getTestSetTests(
    testSetId: string,
    params: TestSetsQueryParams = {}
  ): Promise<PaginatedResponse<TestDetail>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };

    return this.fetchPaginated<TestDetail>(
      `${API_ENDPOINTS.testSets}/${testSetId}/tests`,
      paginationParams,
      {
        cache: 'no-store',
      }
    );
  }

  async downloadTestSet(testSetId: string): Promise<Blob> {
    return this.fetchBlob(`${API_ENDPOINTS.testSets}/${testSetId}/download`);
  }

  /**
   * Get metrics associated with a test set.
   * When a test set has associated metrics, those metrics override the default
   * behavior-level metrics during test execution.
   *
   * @param testSetId - The test set identifier
   * @returns List of metrics associated with the test set (empty array if none)
   */
  async getTestSetMetrics(testSetId: string): Promise<TestSetMetric[]> {
    return this.fetch<TestSetMetric[]>(
      `${API_ENDPOINTS.testSets}/${testSetId}/metrics`,
      {
        cache: 'no-store',
      }
    );
  }

  /**
   * Add a metric to a test set.
   * When a test set has associated metrics, those metrics override the default
   * behavior-level metrics during test execution.
   *
   * @param testSetId - The test set identifier
   * @param metricId - The metric ID to add
   * @returns Updated list of metrics associated with the test set
   */
  async addMetricToTestSet(
    testSetId: string,
    metricId: string
  ): Promise<TestSetMetric[]> {
    return this.fetch<TestSetMetric[]>(
      `${API_ENDPOINTS.testSets}/${testSetId}/metrics/${metricId}`,
      {
        method: 'POST',
      }
    );
  }

  /**
   * Remove a metric from a test set.
   *
   * @param testSetId - The test set identifier
   * @param metricId - The metric ID to remove
   * @returns Updated list of metrics associated with the test set
   */
  async removeMetricFromTestSet(
    testSetId: string,
    metricId: string
  ): Promise<TestSetMetric[]> {
    return this.fetch<TestSetMetric[]>(
      `${API_ENDPOINTS.testSets}/${testSetId}/metrics/${metricId}`,
      {
        method: 'DELETE',
      }
    );
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
      credentials: 'include',
    });

    if (!response.ok) {
      let errorMessage = '';
      let errorData: any;

      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          errorData = await response.json();
          if (errorData.detail) {
            errorMessage = Array.isArray(errorData.detail)
              ? errorData.detail
                  .map(
                    (err: any) => `${err.loc?.join('.') || 'field'}: ${err.msg}`
                  )
                  .join(', ')
              : errorData.detail;
          } else if (errorData.message) {
            errorMessage = errorData.message;
          } else {
            errorMessage = JSON.stringify(errorData, null, 2);
          }
        } else {
          errorMessage = await response.text();
        }
      } catch (parseError) {
        errorMessage = await response.text();
      }

      const error = new Error(
        `API error: ${response.status} - ${errorMessage}`
      ) as Error & {
        status?: number;
        data?: any;
      };
      error.status = response.status;
      error.data = errorData;
      throw error;
    }

    return response.blob();
  }
}
