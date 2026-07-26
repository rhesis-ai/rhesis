'use client';

import * as React from 'react';
import { useSession } from 'next-auth/react';
import type { PaginatedResponse } from '@/utils/api-client/interfaces/pagination';
import { isAuthenticated, isSessionLoading } from './useIsAuthenticated';

export interface UsePaginatedListOptions<T> {
  /** Fetches one page for the given offset/size. Should close over any active filters. */
  fetchPage: (params: {
    skip: number;
    limit: number;
  }) => Promise<PaginatedResponse<T>>;
  /**
   * Stable string capturing all active filter state. Changing it resets the
   * page to 0 and triggers a re-fetch, same as changing `page`/`rowsPerPage`.
   */
  filterFingerprint: string;
  /** Server-fetched first page, when present skips the initial client fetch. */
  initialData?: T[];
  initialTotalCount?: number;
  defaultPageSize?: number;
  /**
   * Called with each successful page's data, in addition to `data` being
   * updated. Use this to accumulate filter-dropdown options or other
   * derived state that shouldn't reset every fetch.
   */
  onData?: (data: T[]) => void;
  /** Called with the raw error on fetch failure, e.g. to show a toast. */
  onError?: (error: unknown) => void;
}

export interface UsePaginatedListResult<T> {
  data: T[];
  setData: React.Dispatch<React.SetStateAction<T[]>>;
  totalCount: number;
  /** Escape hatch for optimistic create/delete: adjust the count shown by pagination controls without a re-fetch. */
  setTotalCount: React.Dispatch<React.SetStateAction<number>>;
  isLoading: boolean;
  error: string | null;
  page: number;
  rowsPerPage: number;
  onPageChange: (page: number) => void;
  onRowsPerPageChange: (size: number) => void;
  refresh: () => void;
}

/**
 * Owns the client-side half of the server-pagination pattern shared by
 * directory-style pages (metrics, behaviors, ...): page/rowsPerPage state,
 * resetting to page 0 on filter change, clamping the page when the result
 * set shrinks (e.g. after a delete), and re-fetching on page/filter/refresh
 * changes.
 *
 * Fetches are keyed by a request signature (page, rowsPerPage,
 * filterFingerprint, refreshKey, sessionStatus) rather than a one-shot
 * "skip the first fetch" flag, so it stays correct under React 18 Strict
 * Mode's dev-only double-invoke of mount effects: both invocations compute
 * the same signature and both no-op, instead of the second slipping through
 * a "consumed" ref. `sessionStatus` is part of the key so a run that lands
 * while the session is still `loading` doesn't "claim" the same key a later
 * `authenticated` run would use.
 */
export function usePaginatedList<T>({
  fetchPage,
  filterFingerprint,
  initialData,
  initialTotalCount = 0,
  defaultPageSize = 25,
  onData,
  onError,
}: UsePaginatedListOptions<T>): UsePaginatedListResult<T> {
  const { status: sessionStatus } = useSession();

  const [data, setData] = React.useState<T[]>(initialData ?? []);
  const [totalCount, setTotalCount] = React.useState(initialTotalCount);
  const [isLoading, setIsLoading] = React.useState(initialData === undefined);
  const [error, setError] = React.useState<string | null>(null);

  const [page, setPage] = React.useState(0);
  const [rowsPerPage, setRowsPerPage] = React.useState(defaultPageSize);
  const [refreshKey, setRefreshKey] = React.useState(0);

  const loadedRequestKeyRef = React.useRef<string | null>(
    initialData !== undefined
      ? `${page}|${rowsPerPage}|${filterFingerprint}|${refreshKey}|${sessionStatus}`
      : null
  );

  React.useEffect(() => {
    setPage(0);
  }, [filterFingerprint]);

  React.useEffect(() => {
    const requestKey = `${page}|${rowsPerPage}|${filterFingerprint}|${refreshKey}|${sessionStatus}`;
    if (loadedRequestKeyRef.current === requestKey) {
      return;
    }
    loadedRequestKeyRef.current = requestKey;

    let cancelled = false;

    const run = async () => {
      if (!isAuthenticated(sessionStatus)) {
        if (!isSessionLoading(sessionStatus)) {
          setIsLoading(false);
        }
        return;
      }

      try {
        setIsLoading(true);
        setError(null);

        const response = await fetchPage({
          skip: page * rowsPerPage,
          limit: rowsPerPage,
        });

        if (cancelled) return;

        setData(response.data);
        setTotalCount(response.pagination.totalCount);
        onData?.(response.data);
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : 'An error occurred';
        setError(message);
        onError?.(err);
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    run();
    return () => {
      cancelled = true;
    };
    // fetchPage/onData/onError are recreated every render; the request-key
    // check above (not this array) is what governs whether a fetch actually
    // fires, so omitting them here is intentional -- adding them would only
    // cause spurious re-runs on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, rowsPerPage, filterFingerprint, refreshKey, sessionStatus]);

  // Clamp page when the result set shrinks below the current page (e.g. after delete)
  React.useEffect(() => {
    if (totalCount === 0) return;
    const lastPage = Math.max(0, Math.ceil(totalCount / rowsPerPage) - 1);
    if (page > lastPage) {
      setPage(lastPage);
    }
  }, [totalCount, rowsPerPage, page]);

  const refresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const onPageChange = React.useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  const onRowsPerPageChange = React.useCallback((newSize: number) => {
    setRowsPerPage(newSize);
    setPage(0);
  }, []);

  return {
    data,
    setData,
    totalCount,
    setTotalCount,
    isLoading,
    error,
    page,
    rowsPerPage,
    onPageChange,
    onRowsPerPageChange,
    refresh,
  };
}
