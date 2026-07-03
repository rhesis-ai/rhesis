'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { Alert, Box, Typography } from '@mui/material';
import TracesTable from './TracesTable';
import TraceDrawer from './TraceDrawer';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TraceQueryParams } from '@/utils/api-client/interfaces/telemetry';
import { useGridQuery } from '@/hooks/useGridQuery';
import { traceKeys } from '@/constants/query-keys';
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
  onUnfilteredEmpty,
}: TracesClientProps) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { activeProject, loading: projectLoading } = useActiveProject();
  const scopedProjectId = activeProject?.id
    ? String(activeProject.id)
    : readActiveProjectId();

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

  const {
    data,
    isFetching,
    error: fetchError,
  } = useGridQuery({
    queryKey: traceKeys.list({ ...queryParams, scopedProjectId }),
    queryFn: () => {
      if (!scopedProjectId)
        return Promise.reject(new Error('No active project'));
      const clientFactory = new ApiClientFactory(sessionToken, scopedProjectId);
      return clientFactory.getTelemetryClient().listTraces(queryParams);
    },
    enabled: !!sessionToken && !projectLoading && !!scopedProjectId,
  });

  const traces = data?.traces ?? [];
  const totalCount = data?.total ?? 0;
  const error = fetchError ? 'Failed to fetch traces' : null;
  const listLoading = isFetching || projectLoading;

  useEffect(() => {
    const unfiltered =
      typeFilter === 'all' &&
      !searchQuery.trim() &&
      !hasActiveTraceDrawerFilters(drawerFilters, {
        testRunScope: Boolean(fixedTestRunId),
        excludeTestRunId: Boolean(fixedTestRunId),
      });
    onUnfilteredEmpty?.(
      !listLoading && !!scopedProjectId && totalCount === 0 && unfiltered
    );
  }, [
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

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: traceKeys.all() });
  }, [queryClient]);

  const showFilteredEmpty =
    !listLoading && traces.length === 0 && totalCount === 0;

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
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
