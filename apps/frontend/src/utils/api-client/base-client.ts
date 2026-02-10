import { API_CONFIG, API_ENDPOINTS } from './config';
import {
  PaginationParams,
  PaginatedResponse,
} from './interfaces/pagination';
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
    const backoffMs =
      this.retryConfig.initialDelayMs *
      Math.pow(this.retryConfig.backoffMultiplier, attempt - 1);
    return Math.min(backoffMs, this.retryConfig.maxDelayMs);
  }

  private isRetryableError(error: any): boolean {
    // Check if error has a status code
    if (error instanceof Error && 'status' in error) {
      const status = (error as any).status;

      // Don't retry client errors (4xx) - these indicate problems that won't be fixed by retrying
      // This includes: 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, etc.
      if (status >= 400 && status < 500) {
        return false;
      }

      // Retry server errors (5xx) - these might be transient
      if (status >= 500 && status < 600) {
        return true;
      }
    }

    // Don't retry if error message indicates a non-retryable error
    if (
      error instanceof Error &&
      (error.message.includes('Unauthorized') ||
        error.message.includes('Forbidden') ||
        error.message.includes('access denied') ||
        error.message.toLowerCase().includes('permission'))
    ) {
      return false;
    }

    // Retry on network errors (connection issues)
    if (
      error instanceof TypeError &&
      error.message.includes('Failed to fetch')
    ) {
      return true;
    }

    // Don't retry by default
    return false;
  }

  private async handleUnauthorizedError(status: number = 401): Promise<never> {
    // Create an error with status property to prevent retries
    const createUnauthorizedError = (message: string) => {
      const error = new Error(message) as Error & { status: number };
      error.status = status;
      return error;
    };

    // On server side, just throw a clean unauthorized error
    // Let the middleware handle the redirection
    if (typeof window === 'undefined') {
      throw createUnauthorizedError('Unauthorized');
    }

    // Prevent multiple simultaneous session clearing on client side
    if (isSessionClearing) {
      // Instead of throwing an error, just wait and throw unauthorized
      await this.delay(1000);
      throw createUnauthorizedError('Unauthorized');
    }

    isSessionClearing = true;

    try {
      // Don't interfere if we're already on logout/signin pages
      const currentPath = window.location.pathname;
      if (
        currentPath.includes('/auth/signout') ||
        currentPath.includes('/auth/signin') ||
        currentPath === '/'
      ) {
        throw createUnauthorizedError('Unauthorized');
      }

      // Add a delay to ensure any pending operations complete
      await this.delay(500);
      await clearAllSessionData(); // This now redirects to home page

      // This line should never be reached as clearAllSessionData redirects
      throw createUnauthorizedError('Unauthorized - session cleared');
    } catch (_error) {
      // Throw clean error instead of re-throwing complex error
      throw createUnauthorizedError('Unauthorized');
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
  protected extractTotalCount(
    response: Response,
    defaultValue: number = 0
  ): number {
    try {
      const totalCount = response.headers.get('x-total-count');
      if (!totalCount) {
        return defaultValue;
      }

      const parsed = parseInt(totalCount, 10);
      return isNaN(parsed) ? defaultValue : parsed;
    } catch (_error) {
      return defaultValue;
    }
  }

  protected async fetch<T>(
    endpoint: keyof typeof API_ENDPOINTS | string,
    options: RequestInit = {}
  ): Promise<T> {
    const path =
      API_ENDPOINTS[endpoint as keyof typeof API_ENDPOINTS] || endpoint;
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
          // Determine if this is an expected validation/client error or an unexpected server error
          // 404 Not Found and 410 Gone are expected states for missing/deleted items
          const isClientError = [400, 404, 409, 410, 422, 429].includes(
            response.status
          );
          const logLevel = isClientError ? 'warn' : 'error';
          const logPrefix = isClientError ? '[VALIDATION]' : '[ERROR]';

          // Don't log 404/410 in development - they're expected states handled by error boundary
          const shouldLog = !(
            process.env.FRONTEND_ENV === 'development' &&
            [404, 410].includes(response.status)
          );

          if (shouldLog) {
            console[logLevel](`${logPrefix} [DEBUG] API Response Error:`, {
              url,
              status: response.status,
              statusText: response.statusText,
              headers: Object.fromEntries(response.headers.entries()),
            });
          }

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
                        (err: any) =>
                          `${err.loc?.join('.') || 'field'}: ${err.msg}`
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
          } catch (_parseError) {
            errorMessage = await response.text();
          }

          if (shouldLog) {
            console[logLevel](`${logPrefix} [DEBUG] Full error details:`, {
              errorMessage,
              errorData,
            });
          }

          // Provide user-friendly messages for rate limiting
          if (response.status === 429) {
            const rateLimitInfo = errorMessage; // e.g., "10 per 1 hour"
            errorMessage = `Too many requests. You've exceeded the rate limit (${rateLimitInfo}). Please try again later.`;
          }

          // For 410 Gone and 404 Not Found responses, encode critical data in the message
          // so it survives serialization across Next.js server-client boundary
          let enhancedMessage = errorMessage;
          if (response.status === 410 || response.status === 404) {
            const parts: string[] = [];

            // Include table_name (critical for restore operations)
            if (errorData?.table_name) {
              parts.push(`table:${errorData.table_name}`);
            }

            // Include item_id
            if (errorData?.item_id) {
              parts.push(`id:${errorData.item_id}`);
            }

            // Include item_name if available (for display)
            if (errorData?.item_name) {
              parts.push(`name:${errorData.item_name}`);
            }

            // Format: "table:test_run|id:abc-123|name:My Test|Original message"
            if (parts.length > 0) {
              enhancedMessage = `${parts.join('|')}|${errorMessage}`;
            }
          }

          const error = new Error(
            `API error: ${response.status} - ${enhancedMessage}`
          ) as Error & {
            status?: number;
            data?: any;
          };
          error.status = response.status;
          error.data = errorData;

          // Handle authentication errors
          if (response.status === 401 || response.status === 403) {
            return await this.handleUnauthorizedError(response.status);
          }

          throw error;
        }

        // For 204 No Content or empty responses, return undefined as T
        if (
          response.status === 204 ||
          response.headers.get('content-length') === '0'
        ) {
          return undefined as unknown as T;
        }

        const result = await response.json();
        return result;
      } catch (error: any) {
        lastError = error;

        // Handle authentication errors immediately without retrying
        if (error.status === 401 || error.status === 403) {
          return await this.handleUnauthorizedError(error.status);
        }

        // Handle deleted entities (410 Gone) immediately without retrying
        if (error.status === 410) {
          throw error;
        }

        // If this is the last attempt or error is not retryable, throw the error
        if (
          attempt === this.retryConfig.maxAttempts ||
          !this.isRetryableError(error)
        ) {
          if (
            error instanceof TypeError &&
            error.message.includes('Failed to fetch')
          ) {
            throw new Error(
              `Network error when connecting to ${this.baseUrl}. Please check your connection and ensure the API server is running.`
            );
          }

          // Use appropriate log level based on error status
          // 410 Gone is included as it's an expected state for soft-deleted items
          const isClientError =
            error.status && [400, 409, 410, 422, 429].includes(error.status);
          if (isClientError) {
          } else {
          }
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
    params: PaginationParams & { $filter?: string } & Record<string, any> = {
      skip: 0,
      limit: 10,
    },
    options: RequestInit = {}
  ): Promise<PaginatedResponse<T>> {
    const queryParams = new URLSearchParams();
    if (params.skip !== undefined)
      queryParams.append('skip', params.skip.toString());
    if (params.limit !== undefined)
      queryParams.append('limit', params.limit.toString());
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);
    if (params.$filter) queryParams.append('$filter', params.$filter);

    // Add any additional parameters (excluding the ones we've already handled)
    const excludedParams = [
      'skip',
      'limit',
      'sort_by',
      'sort_order',
      '$filter',
    ];
    Object.keys(params).forEach(key => {
      if (!excludedParams.includes(key) && params[key] !== undefined) {
        queryParams.append(key, params[key].toString());
      }
    });

    const path =
      API_ENDPOINTS[endpoint as keyof typeof API_ENDPOINTS] || endpoint;
    const queryString = queryParams.toString();
    const url = joinUrl(
      this.baseUrl,
      queryString ? `${path}?${queryString}` : path
    );

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
          errorMessage =
            errorData.detail || errorData.message || JSON.stringify(errorData);
        } else {
          errorMessage = await response.text();
        }
      } catch (_parseError) {
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

      // Handle authentication errors
      if (response.status === 401 || response.status === 403) {
        return await this.handleUnauthorizedError(response.status);
      }

      throw error;
    }

    const totalCount = this.extractTotalCount(response);
    const data = (await response.json()) as T[];
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
        totalPages,
      },
    };
  }
}
