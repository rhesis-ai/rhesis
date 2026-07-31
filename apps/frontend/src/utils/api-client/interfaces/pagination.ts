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
  /** OData $filter expression */
  $filter?: string;
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
