import { API_CONFIG, API_ENDPOINTS } from './config';
import { PaginationParams, PaginatedResponse, PaginationMetadata } from './interfaces/pagination';
import { joinUrl } from '@/utils/url';
import { clearAllSessionData } from '../session';

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

// Flag to prevent multiple simultaneous session clearing
let isSessionClearing = false;

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
    // Don't retry authentication errors
    if (error instanceof Error && 'status' in error) {
      const status = (error as any).status;
      if (status === 401 || status === 403) {
        return false;
      }
    }
    
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

  private async handleUnauthorizedError(): Promise<never> {
    // On server side, just throw a clean unauthorized error
    // Let the middleware handle the redirection
    if (typeof window === 'undefined') {
      throw new Error('Unauthorized');
    }

    // Prevent multiple simultaneous session clearing on client side
    if (isSessionClearing) {
      // Instead of throwing an error, just wait and throw unauthorized
      await this.delay(1000);
      throw new Error('Unauthorized');
    }
    
    isSessionClearing = true;
    
    try {
      console.log('🔴 Unauthorized error detected in API client, checking current location...');
      
      // Don't interfere if we're already on logout/signin pages
      const currentPath = window.location.pathname;
      if (currentPath.includes('/auth/signout') || currentPath.includes('/auth/signin') || currentPath === '/') {
        console.log('🔴 Already on auth page, skipping session clearing');
        throw new Error('Unauthorized');
      }
      
      console.log('🔴 Clearing session due to unauthorized API response...');
      
      // Add a delay to ensure any pending operations complete
      await this.delay(500);
      await clearAllSessionData(); // This now redirects to home page
      
      // This line should never be reached as clearAllSessionData redirects
      throw new Error('Unauthorized - session cleared');
    } catch (error) {
      console.error('Error during session clearing:', error);
      throw new Error('Unauthorized'); // Throw clean error instead of re-throwing complex error
    } finally {
      // Reset the flag after a delay
      setTimeout(() => {
        isSessionClearing = false;
      }, 2000);
    }
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
          
          // Handle authentication errors
          if (response.status === 401 || response.status === 403) {
            return await this.handleUnauthorizedError();
          }
          
          throw error;
        }

        // For 204 No Content or empty responses, return undefined as T
        if (response.status === 204 || response.headers.get('content-length') === '0') {
          return undefined as unknown as T;
        }

        return response.json();
      } catch (error: any) {
        lastError = error;
        
        // Handle authentication errors immediately without retrying
        if (error.status === 401 || error.status === 403) {
          return await this.handleUnauthorizedError();
        }
        
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
    params: PaginationParams & { $filter?: string } & Record<string, any> = { skip: 0, limit: 10 },
    options: RequestInit = {}
  ): Promise<PaginatedResponse<T>> {
    const queryParams = new URLSearchParams();
    if (params.skip !== undefined) queryParams.append('skip', params.skip.toString());
    if (params.limit !== undefined) queryParams.append('limit', params.limit.toString());
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);
    if (params.$filter) queryParams.append('$filter', params.$filter);
    
    // Add any additional parameters (excluding the ones we've already handled)
    const excludedParams = ['skip', 'limit', 'sort_by', 'sort_order', '$filter'];
    Object.keys(params).forEach(key => {
      if (!excludedParams.includes(key) && params[key] !== undefined) {
        queryParams.append(key, params[key].toString());
      }
    });

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
      
      // Handle authentication errors
      if (response.status === 401 || response.status === 403) {
        return await this.handleUnauthorizedError();
      }
      
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