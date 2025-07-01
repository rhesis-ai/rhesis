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
  GenerationSample,
  TestSetGenerationConfig,
  TestSetGenerationRequest,
  TestSetGenerationResponse
} from './interfaces/test-set';
import { TestDetail, PriorityLevel } from './interfaces/tests';
import { StatusClient } from './status-client';
import { PaginatedResponse, PaginationParams } from './interfaces/pagination';

interface TestSetsQueryParams extends Partial<PaginationParams> {
  // Add any additional test-set specific query params here
}

const DEFAULT_PAGINATION: PaginationParams = {
  skip: 0,
  limit: 50,  // Update default limit to match requirement
      sort_by: 'created_at',
    sort_order: 'desc'
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
  private numericToPriorityString(priorityNum: number | undefined): PriorityLevel {
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
      // @ts-ignore - We're adding a string priority property
      result.priorityLevel = this.numericToPriorityString(result.priority);
    }
    return result;
  }

  async generateTestSet(request: TestSetGenerationRequest): Promise<TestSetGenerationResponse> {
    return this.fetch<TestSetGenerationResponse>(`${API_ENDPOINTS.testSets}/generate`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getTestSets(params: TestSetsQueryParams = {}): Promise<PaginatedResponse<TestSet>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };
    
    const response = await this.fetchPaginated<TestSet>(
      API_ENDPOINTS.testSets,
      paginationParams,
      {
        cache: 'no-store'
      }
    );

    // Convert numeric priorities to string values
    return {
      ...response,
      data: response.data.map(testSet => this.convertTestSetPriority(testSet))
    };
  }

  async getTestSet(identifier: string): Promise<TestSet> {
    const testSet = await this.fetch<TestSet>(`${API_ENDPOINTS.testSets}/${identifier}`);
    // Convert numeric priority to string value
    return this.convertTestSetPriority(testSet);
  }

  async getTestSetStats(options: StatsOptions = {}): Promise<TestSetStatsResponse> {
    const { top, months, mode } = options;
    
    const queryString = buildQueryParams({
      top,
      months,
      mode
    });
    
    const url = `${API_ENDPOINTS.testSets}/stats${queryString}`;
    
    return this.fetch<TestSetStatsResponse>(url, {
      cache: 'no-store'
    });
  }
  
  async getTestSetDetailStats(identifier: string, options: StatsOptions = {}): Promise<TestSetDetailStatsResponse> {
    const { top, months, mode } = options;
    
    const queryString = buildQueryParams({
      top,
      months,
      mode
    });
    
    const url = `${API_ENDPOINTS.testSets}/${identifier}/stats${queryString}`;
    
    return this.fetch<TestSetDetailStatsResponse>(url, {
      cache: 'no-store'
    });
  }

  async createTestSet(testSet: TestSetCreate): Promise<TestSet> {
    return this.fetch<TestSet>(API_ENDPOINTS.testSets, {
      method: 'POST',
      body: JSON.stringify(testSet),
    });
  }

  async updateTestSet(id: string, testSet: Partial<TestSetCreate>): Promise<TestSet> {
    const updatedTestSet = await this.fetch<TestSet>(`${API_ENDPOINTS.testSets}/${id}`, {
      method: 'PUT',
      body: JSON.stringify(testSet),
    });

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
    testConfigurationAttributes?: { execution_mode?: string; [key: string]: any }
  ): Promise<TestSet> {
    const requestBody = testConfigurationAttributes ? { execution_options: testConfigurationAttributes } : undefined;
    
    return this.fetch<TestSet>(`${API_ENDPOINTS.testSets}/${testSetId}/execute/${endpointId}`, {
      method: 'POST',
      body: requestBody ? JSON.stringify(requestBody) : undefined,
      headers: requestBody ? { 'Content-Type': 'application/json' } : undefined
    });
  }
  
  async createTestSetBulk(testSetData: TestSetBulkCreate): Promise<TestSetBulkResponse> {
    return this.fetch<TestSetBulkResponse>(`${API_ENDPOINTS.testSets}/bulk`, {
      method: 'POST',
      body: JSON.stringify(testSetData),
    });
  }

  async associateTestsWithTestSet(testSetId: string, testIds: string[]): Promise<TestSetBulkAssociateResponse> {
    const request: TestSetBulkAssociateRequest = {
      test_ids: testIds as any[], // Type conversion from string[] to UUID[]
    };
    
    return this.fetch<TestSetBulkAssociateResponse>(`${API_ENDPOINTS.testSets}/${testSetId}/associate`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async disassociateTestsFromTestSet(testSetId: string, testIds: string[]): Promise<TestSetBulkDisassociateResponse> {
    const request: TestSetBulkDisassociateRequest = {
      test_ids: testIds as any[], // Type conversion from string[] to UUID[]
    };
    
    return this.fetch<TestSetBulkDisassociateResponse>(`${API_ENDPOINTS.testSets}/${testSetId}/disassociate`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getTestSetTests(testSetId: string, params: TestSetsQueryParams = {}): Promise<PaginatedResponse<TestDetail>> {
    const paginationParams = { ...DEFAULT_PAGINATION, ...params };
    
    return this.fetchPaginated<TestDetail>(
      `${API_ENDPOINTS.testSets}/${testSetId}/tests`,
      paginationParams,
      {
        cache: 'no-store'
      }
    );
  }

  async downloadTestSet(testSetId: string): Promise<Blob> {
    return this.fetchBlob(`${API_ENDPOINTS.testSets}/${testSetId}/download`);
  }

  protected async fetchBlob(
    endpoint: keyof typeof API_ENDPOINTS | string,
    options: RequestInit = {}
  ): Promise<Blob> {
    const path = API_ENDPOINTS[endpoint as keyof typeof API_ENDPOINTS] || endpoint;
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
              ? errorData.detail.map((err: any) => `${err.loc?.join('.') || 'field'}: ${err.msg}`).join(', ')
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
      
      const error = new Error(`API error: ${response.status} - ${errorMessage}`) as Error & { 
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