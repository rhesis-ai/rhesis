/**
 * Parameters for paginated API requests
 */
export interface PaginationParams {
  /** Number of items to skip (offset) */
  skip: number;
  /** Maximum number of items to return */
  limit: number;
  /** Field to sort by */
  sort_by?: string;
  /** Sort order ('asc' or 'desc') */
  sort_order?: 'asc' | 'desc';
}

/**
 * Metadata about the current pagination state
 */
export interface PaginationMetadata {
  /** Total number of items available */
  totalCount: number;
  /** Current page number (0-based) */
  currentPage: number;
  /** Number of items per page */
  pageSize: number;
  /** Total number of pages available */
  totalPages: number;
}

/**
 * Generic interface for paginated API responses
 */
export interface PaginatedResponse<T> {
  /** Array of items for the current page */
  data: T[];
  /** Pagination metadata */
  pagination: {
    totalCount: number;
    skip: number;
    limit: number;
    currentPage: number;
    pageSize: number;
    totalPages: number;
  };
}
