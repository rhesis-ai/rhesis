'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Alert, Box, Typography } from '@mui/material';
import TracesTable from './TracesTable';
import TraceDrawer from './TraceDrawer';
import { useList } from '@/hooks/useList';
import { tracesList } from './list';
import type { TraceSummary } from '@/utils/api-client/interfaces/telemetry';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { readActiveProjectId } from '@/utils/active-project';
import {
  EMPTY_TRACE_DRAWER_FILTERS,
  hasActiveTraceDrawerFilters,
  sanitizeTraceDrawerFiltersForTestRunScope,
  type TraceDrawerFilters,
} from './trace-filter-params';

interface TracesClientProps {
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
  initialTraceId?: string | null;
  initialProjectId?: string | null;
  fixedTestRunId?: string;
  onUnfilteredEmpty?: (empty: boolean) => void;
  /** Bumped by the wrapper's refresh FAB, to trigger a re-fetch. */
  refreshTrigger?: number;
  /** Server-fetched first page -- when present, skips the initial client fetch. */
  initialData?: TraceSummary[];
  initialTotalCount?: number;
}

export default function TracesClient({
  currentUserId = '',
  currentUserName = '',
  currentUserPicture,
  initialTraceId = null,
  initialProjectId = null,
  fixedTestRunId,
  onUnfilteredEmpty,
  refreshTrigger,
  initialData,
  initialTotalCount,
}: TracesClientProps) {
  const router = useRouter();
  const pathname = usePathname();
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
  const [errorDismissed, setErrorDismissed] = useState(false);

  const descriptor = useMemo(
    () => tracesList(scopedProjectId),
    [scopedProjectId]
  );

  const filters = useMemo(
    () => ({
      search: searchQuery,
      typeFilter,
      projectId: drawerFilters.projectId ?? '',
      endpointId: drawerFilters.endpointId ?? '',
      environment: drawerFilters.environment ?? '',
      timeRange: drawerFilters.timeRange,
      startTimeAfter: drawerFilters.startTimeAfter ?? '',
      startTimeBefore: drawerFilters.startTimeBefore ?? '',
      traceSource: drawerFilters.traceSource ?? '',
      traceMetricsStatus: drawerFilters.traceMetricsStatus ?? '',
      testRunId: drawerFilters.testRunId ?? '',
      testResultId: drawerFilters.testResultId ?? '',
      testId: drawerFilters.testId ?? '',
    }),
    [searchQuery, typeFilter, drawerFilters]
  );

  const {
    data: traces,
    totalCount,
    isLoading,
    error: rawError,
    refresh,
    page,
    rowsPerPage: pageSize,
    onPageChange,
    onRowsPerPageChange,
  } = useList(descriptor, {
    filters,
    enabled: !projectLoading && !!scopedProjectId,
    initialData,
    initialTotalCount,
    onError: () => setErrorDismissed(false),
  });

  useEffect(() => {
    setErrorDismissed(false);
  }, [rawError]);

  const error = rawError && !errorDismissed ? rawError : null;
  const dismissError = useCallback(() => setErrorDismissed(true), []);

  const isFirstRefreshTrigger = useRef(true);
  useEffect(() => {
    if (isFirstRefreshTrigger.current) {
      isFirstRefreshTrigger.current = false;
      return;
    }
    refresh();
    // Only refreshTrigger (bumped by the wrapper's refresh FAB) should re-run this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  const listLoading = isLoading || projectLoading;

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

  const showFilteredEmpty =
    !listLoading && traces.length === 0 && totalCount === 0;

  return (
    <>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={dismissError}>
          {error}
        </Alert>
      )}

      <TracesTable
        traces={traces}
        loading={listLoading}
        onRowClick={handleRowClick}
        totalCount={totalCount}
        page={page}
        pageSize={pageSize}
        onPageChange={onPageChange}
        onPageSizeChange={onRowsPerPageChange}
        searchQuery={searchQuery}
        onSearchQueryChange={setSearchQuery}
        typeFilter={typeFilter}
        onTypeFilterChange={setTypeFilter}
        drawerFilters={drawerFilters}
        onApplyDrawerFilters={handleApplyDrawerFilters}
        filterDrawerOpen={filterDrawerOpen}
        onFilterDrawerOpen={() => setFilterDrawerOpen(true)}
        onFilterDrawerClose={() => setFilterDrawerOpen(false)}
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
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        currentUserPicture={currentUserPicture}
        onTraceUpdated={refresh}
      />
    </>
  );
}
