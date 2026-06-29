'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Alert, Box, Typography } from '@mui/material';
import TracesTable from './TracesTable';
import TraceDrawer from './TraceDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TraceSummary,
  TraceQueryParams,
} from '@/utils/api-client/interfaces/telemetry';
import { useNotifications } from '@/components/common/NotificationContext';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { readActiveProjectId } from '@/utils/active-project';
import {
  buildTraceQueryParams,
  EMPTY_TRACE_DRAWER_FILTERS,
  hasActiveTraceDrawerFilters,
  sanitizeTraceDrawerFiltersForTestRunScope,
  type TraceDrawerFilters,
} from './trace-filter-params';

const TRACE_PAGE_SIZE_OPTIONS = [25, 50, 100];

function normalizePageSize(size: number): number {
  return TRACE_PAGE_SIZE_OPTIONS.includes(size) ? size : 50;
}

interface TracesClientProps {
  sessionToken: string;
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
  initialTraceId?: string | null;
  initialProjectId?: string | null;
  fixedTestRunId?: string;
  refreshKey?: number;
  onRefresh?: () => void;
  onUnfilteredEmpty?: (empty: boolean) => void;
}

export default function TracesClient({
  sessionToken,
  currentUserId = '',
  currentUserName = '',
  currentUserPicture,
  initialTraceId = null,
  initialProjectId = null,
  fixedTestRunId,
  refreshKey: externalRefreshKey = 0,
  onRefresh,
  onUnfilteredEmpty,
}: TracesClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const notifications = useNotifications();
  const { activeProject, loading: projectLoading } = useActiveProject();
  const scopedProjectId = activeProject?.id
    ? String(activeProject.id)
    : readActiveProjectId();
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasFetchedOnce, setHasFetchedOnce] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);

  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(
    initialTraceId
  );
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    initialProjectId
  );
  const [drawerOpen, setDrawerOpen] = useState(
    !!(initialTraceId && initialProjectId)
  );

  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [drawerFilters, setDrawerFilters] = useState<TraceDrawerFilters>(() =>
    fixedTestRunId
      ? sanitizeTraceDrawerFiltersForTestRunScope(
          EMPTY_TRACE_DRAWER_FILTERS,
          fixedTestRunId
        )
      : {
          ...EMPTY_TRACE_DRAWER_FILTERS,
          ...(initialProjectId ? { projectId: initialProjectId } : {}),
        }
  );
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  const pageSize = normalizePageSize(limit);

  const queryParams: TraceQueryParams = useMemo(
    () => ({
      ...buildTraceQueryParams(
        drawerFilters,
        searchQuery,
        typeFilter,
        pageSize,
        offset
      ),
      // Traces are project-scoped (fail-closed). Always filter by the active
      // project unless the drawer explicitly overrides it.
      ...(scopedProjectId && !drawerFilters.projectId
        ? { project_id: scopedProjectId }
        : {}),
    }),
    [drawerFilters, searchQuery, typeFilter, pageSize, offset, scopedProjectId]
  );

  const listLoading = loading || projectLoading;

  useEffect(() => {
    let cancelled = false;

    const fetchTraces = async () => {
      if (!sessionToken || projectLoading) return;

      // Traces are project-scoped (fail-closed RLS). Wait for active project
      // resolution before fetching — the cookie may not exist on first paint.
      if (!scopedProjectId) {
        setTraces([]);
        setTotalCount(0);
        setHasFetchedOnce(false);
        setLoading(false);
        return;
      }

      setHasFetchedOnce(false);
      setLoading(true);
      setError(null);

      try {
        const clientFactory = new ApiClientFactory(
          sessionToken,
          scopedProjectId
        );
        const client = clientFactory.getTelemetryClient();
        const response = await client.listTraces(queryParams);
        if (cancelled) return;
        setTraces(response.traces);
        setTotalCount(response.total);
        setError(null);
      } catch (err: unknown) {
        if (cancelled) return;
        const errorMsg =
          err instanceof Error ? err.message : 'Failed to fetch traces';
        setError(errorMsg);
        notifications.show(errorMsg, { severity: 'error' });
        setTraces([]);
        setTotalCount(0);
      } finally {
        if (!cancelled) {
          setHasFetchedOnce(true);
          setLoading(false);
        }
      }
    };

    fetchTraces();

    return () => {
      cancelled = true;
    };
    // notifications intentionally omitted — unstable reference can retrigger fetch
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    sessionToken,
    projectLoading,
    scopedProjectId,
    externalRefreshKey,
    drawerFilters,
    searchQuery,
    typeFilter,
    pageSize,
    offset,
  ]);

  useEffect(() => {
    const unfiltered =
      typeFilter === 'all' &&
      !searchQuery.trim() &&
      !hasActiveTraceDrawerFilters(drawerFilters, {
        testRunScope: Boolean(fixedTestRunId),
        excludeTestRunId: Boolean(fixedTestRunId),
      });
    onUnfilteredEmpty?.(
      hasFetchedOnce &&
        !listLoading &&
        !!scopedProjectId &&
        totalCount === 0 &&
        unfiltered
    );
  }, [
    hasFetchedOnce,
    listLoading,
    scopedProjectId,
    totalCount,
    typeFilter,
    searchQuery,
    drawerFilters,
    fixedTestRunId,
    onUnfilteredEmpty,
  ]);

  useEffect(() => {
    setOffset(0);
  }, [searchQuery, typeFilter, drawerFilters]);

  const handleRowClick = (traceId: string, projectId: string) => {
    setSelectedTraceId(traceId);
    setSelectedProjectId(projectId);
    setDrawerOpen(true);
  };

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setSelectedTraceId(null);
    setSelectedProjectId(null);
    if (initialTraceId) {
      router.replace(pathname, { scroll: false });
    }
  }, [initialTraceId, router, pathname]);

  const handlePageChange = (newPage: number) => {
    setOffset(newPage * pageSize);
  };

  const handlePageSizeChange = (newSize: number) => {
    setLimit(normalizePageSize(newSize));
    setOffset(0);
  };

  const handleApplyDrawerFilters = useCallback(
    (filters: TraceDrawerFilters) => {
      if (fixedTestRunId) {
        setDrawerFilters(
          sanitizeTraceDrawerFiltersForTestRunScope(filters, fixedTestRunId)
        );
        return;
      }
      setDrawerFilters(filters);
    },
    [fixedTestRunId]
  );

  const handleRefresh = () => {
    onRefresh?.();
  };

  const showFilteredEmpty =
    !listLoading && traces.length === 0 && totalCount === 0;

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <TracesTable
        traces={traces}
        loading={listLoading}
        onRowClick={handleRowClick}
        totalCount={totalCount}
        page={Math.floor(offset / pageSize)}
        pageSize={pageSize}
        onPageChange={handlePageChange}
        onPageSizeChange={handlePageSizeChange}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        typeFilter={typeFilter}
        onTypeFilterChange={setTypeFilter}
        drawerFilters={drawerFilters}
        onApplyDrawerFilters={handleApplyDrawerFilters}
        filterDrawerOpen={filterDrawerOpen}
        onFilterDrawerOpen={() => setFilterDrawerOpen(true)}
        onFilterDrawerClose={() => setFilterDrawerOpen(false)}
        sessionToken={sessionToken}
        fixedTestRunId={fixedTestRunId}
      />

      {showFilteredEmpty && (
        <Box sx={{ py: 6, textAlign: 'center' }}>
          <Typography variant="h6" gutterBottom>
            No traces found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Try adjusting your filters or check back after running tests or
            invoking endpoints.
          </Typography>
        </Box>
      )}

      <TraceDrawer
        open={drawerOpen}
        onClose={handleCloseDrawer}
        traceId={selectedTraceId}
        projectId={selectedProjectId || ''}
        sessionToken={sessionToken}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        currentUserPicture={currentUserPicture}
        onTraceUpdated={handleRefresh}
      />
    </>
  );
}
