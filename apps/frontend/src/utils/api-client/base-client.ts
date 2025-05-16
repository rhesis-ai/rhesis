import { API_CONFIG, API_ENDPOINTS } from './config';
import { PaginationParams, PaginatedResponse, PaginationMetadata } from './interfaces/pagination';
import { joinUrl } from '@/utils/url';

interface RetryConfig {
  maxAttempts: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxAttempts: 1,
  initialDelayMs: 1000,
  maxDelayMs: 10000,
  backoffMultiplier: 2,
};

export class BaseApiClient {
  protected baseUrl: string;
  protected sessionToken?: string;
  protected retryConfig: RetryConfig;

  constructor(sessionToken?: string, retryConfig: Partial<RetryConfig> = {}) {
    this.baseUrl = API_CONFIG.baseUrl;
    this.sessionToken = sessionToken;
    this.retryConfig = { ...DEFAULT_RETRY_CONFIG, ...retryConfig };
  }

  protected getHeaders(): HeadersInit {
    const headers: Record<string, string> = { ...API_CONFIG.defaultHeaders };
    
    if (this.sessionToken) {
      headers['Authorization'] = `Bearer ${this.sessionToken}`;
    }
    
    return headers;
  }

  private async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private calculateBackoff(attempt: number): number {
    const backoffMs = this.retryConfig.initialDelayMs * 
      Math.pow(this.retryConfig.backoffMultiplier, attempt - 1);
    return Math.min(backoffMs, this.retryConfig.maxDelayMs);
  }

  private isRetryableError(error: any): boolean {
    // Retry on network errors and 5xx server errors
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
      return true;
    }
    if (error instanceof Error && 'status' in error && typeof (error as any).status === 'number') {
      const status = (error as any).status;
      return status >= 500 && status < 600;
    }
    return false;
  }

  /**
   * Extracts and parses the total count from response headers
   * @param response The fetch Response object
   * @param defaultValue Optional default value if header is not present
   * @returns The parsed total count or defaultValue if header is not present/invalid
   */
  protected extractTotalCount(response: Response, defaultValue: number = 0): number {
    try {
      const totalCount = response.headers.get('x-total-count');
      if (!totalCount) {
        return defaultValue;
      }
      
      const parsed = parseInt(totalCount, 10);
      return isNaN(parsed) ? defaultValue : parsed;
    } catch (error) {
      console.warn('Error parsing x-total-count header:', error);
      return defaultValue;
    }
  }

  protected async fetch<T>(
    endpoint: keyof typeof API_ENDPOINTS | string,
    options: RequestInit = {}
  ): Promise<T> {
    const path = API_ENDPOINTS[endpoint as keyof typeof API_ENDPOINTS] || endpoint;
    const url = joinUrl(this.baseUrl, path);
    const headers = this.getHeaders();

    let lastError: Error | null = null;
    
    for (let attempt = 1; attempt <= this.retryConfig.maxAttempts; attempt++) {
      try {
        const response = await fetch(url, {
          ...options,
          headers: {
            ...headers,
            ...options.headers,
          },
          credentials: 'include', // Include cookies in the request
        });

        if (!response.ok) {
          let errorMessage = '';
          let errorData: any;
          
          try {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
              errorData = await response.json();
              errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData);
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

        // For 204 No Content or empty responses, return undefined as T
        if (response.status === 204 || response.headers.get('content-length') === '0') {
          return undefined as unknown as T;
        }

        return response.json();
      } catch (error: any) {
        lastError = error;
        
        // If this is the last attempt or error is not retryable, throw the error
        if (attempt === this.retryConfig.maxAttempts || !this.isRetryableError(error)) {
          if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
            console.error(`Network error requesting ${url}:`, error);
            throw new Error(`Network error when connecting to ${this.baseUrl}. Please check your connection and ensure the API server is running.`);
          }
          console.error(`API request failed for ${url}:`, error);
          throw error;
        }

        // Calculate and wait for backoff delay before next attempt
        const backoffMs = this.calculateBackoff(attempt);
        await this.delay(backoffMs);
      }
    }

    // This should never be reached due to the throw in the catch block above
    throw lastError;
  }

  /**
   * Fetches paginated data from the API
   * @param endpoint The API endpoint to fetch from
   * @param params Pagination parameters
   * @param options Additional fetch options
   * @returns A paginated response containing both data and pagination metadata
   */
  protected async fetchPaginated<T>(
    endpoint: keyof typeof API_ENDPOINTS | string,
    params: PaginationParams & { $filter?: string } = { skip: 0, limit: 10 },
    options: RequestInit = {}
  ): Promise<PaginatedResponse<T>> {
    const queryParams = new URLSearchParams();
    if (params.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params.sortBy) queryParams.append('sort_by', params.sortBy);
    if (params.sortOrder) queryParams.append('sort_order', params.sortOrder);
    if (params.$filter) queryParams.append('$filter', params.$filter);

    const path = API_ENDPOINTS[endpoint as keyof typeof API_ENDPOINTS] || endpoint;
    const queryString = queryParams.toString();
    const url = joinUrl(this.baseUrl, queryString ? `${path}?${queryString}` : path);

    const response = await fetch(url, {
      ...options,
      headers: {
        ...this.getHeaders(),
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
          errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData);
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

    const totalCount = this.extractTotalCount(response);
    const data = await response.json() as T[];
    const pageSize = params.limit ?? 10;
    const currentPage = Math.floor((params.skip ?? 0) / pageSize);
    const totalPages = Math.ceil(totalCount / pageSize);

    return {
      data,
      pagination: {
        totalCount,
        skip: params.skip ?? 0,
        limit: params.limit ?? pageSize,
        currentPage,
        pageSize,
        totalPages
      }
    };
  }
} 