export type StatsMode = 'entity' | 'related_entity';

export interface StatsOptions {
  top?: number;
  months?: number;
  mode?: StatsMode;  // Default is 'entity' if not specified
}

export interface PaginationParams {
  /** Number of items to skip (offset) */
  skip: number;
  /** Maximum number of items to return */
  limit: number;
  /** Field to sort by */
  sortBy?: string;
  /** Sort order ('asc' or 'desc') */
  sortOrder?: 'asc' | 'desc';
}

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