'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Alert, Box, Paper, Typography } from '@mui/material';
import { GRID_PAPER_SX } from '@/components/common/BaseDataGrid';
import TracesTable from './TracesTable';
import SpansTable from './SpansTable';
import { TracesToolbarContext } from './TracesToolbar';
import TraceDrawer from './TraceDrawer';
import TraceFilterDrawer from './TraceFilterDrawer';
import TraceMetricsSummary from './TraceMetricsSummary';
import { useList } from '@/hooks/useList';
import { tracesList } from './list';
import { spansList, spansListFilters } from './spans-list';
import type {
  SpanSummary,
  TraceSummary,
} from '@/utils/api-client/interfaces/telemetry';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { readActiveProjectId } from '@/utils/active-project';
import {
  buildTraceQueryParams,
  countActiveTraceDrawerFilters,
  EMPTY_TRACE_DRAWER_FILTERS,
  hasActiveTraceDrawerFilters,
  sanitizeTraceDrawerFiltersForTestRunScope,
  type TraceDrawerFilters,
  type TraceView,
} from './trace-filter-params';
import { withTraceUrlState } from './trace-url-state';

interface TracesClientProps {
  currentUserId?: string;
  currentUserName?: string;
  currentUserPicture?: string;
  initialTraceId?: string | null;
  initialProjectId?: string | null;
  /** Span to select when the drawer opens on `initialTraceId`. */
  initialSpanId?: string | null;
  /** Read from the URL on the traces page. */
  initialView?: TraceView;
  /** Read from the URL on the traces page; includes the project filter. */
  initialFilters?: TraceDrawerFilters;
  fixedTestRunId?: string;
  onUnfilteredEmpty?: (empty: boolean) => void;
  /** Bumped by the wrapper's refresh FAB, to trigger a re-fetch. */
  refreshTrigger?: number;
  /** Server-fetched first page of traces -- when present, skips the initial client fetch. */
  initialData?: TraceSummary[];
  initialTotalCount?: number;
}

function initialDrawerFilters(
  fixedTestRunId: string | undefined,
  initialFilters: TraceDrawerFilters | undefined,
  initialProjectId: string | null
): TraceDrawerFilters {
  if (fixedTestRunId) {
    return sanitizeTraceDrawerFiltersForTestRunScope(
      EMPTY_TRACE_DRAWER_FILTERS,
      fixedTestRunId
    );
  }
  if (initialFilters) return initialFilters;
  return {
    ...EMPTY_TRACE_DRAWER_FILTERS,
    ...(initialProjectId ? { projectId: initialProjectId } : {}),
  };
}

export default function TracesClient({
  currentUserId = '',
  currentUserName = '',
  currentUserPicture,
  initialTraceId = null,
  initialProjectId = null,
  initialSpanId = null,
  initialView = 'traces',
  initialFilters,
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

  const [view, setView] = useState<TraceView>(initialView);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(
    initialTraceId
  );
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    initialProjectId
  );
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(
    initialSpanId
  );
  const [drawerOpen, setDrawerOpen] = useState(
    !!(initialTraceId && initialProjectId)
  );

  const [searchQuery, setSearchQuery] = useState('');
  const [drawerFilters, setDrawerFilters] = useState<TraceDrawerFilters>(() =>
    initialDrawerFilters(fixedTestRunId, initialFilters, initialProjectId)
  );
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [errorDismissed, setErrorDismissed] = useState(false);

  // The traces page keeps view and filters in the URL. A run's Traces tab doesn't:
  // that page's URL belongs to its own tabs.
  useEffect(() => {
    if (fixedTestRunId) return;
    const current = new URLSearchParams(window.location.search);
    const next = withTraceUrlState(current, view, drawerFilters);
    if (next.toString() === current.toString()) return;
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, {
      scroll: false,
    });
  }, [view, drawerFilters, fixedTestRunId, pathname, router]);

  const tracesDescriptor = useMemo(
    () => tracesList(scopedProjectId),
    [scopedProjectId]
  );
  const spansDescriptor = useMemo(
    () => spansList(scopedProjectId),
    [scopedProjectId]
  );

  const traceFilters = useMemo(
    () => ({
      search: searchQuery,
      projectId: drawerFilters.projectId ?? '',
      endpointId: drawerFilters.endpointId ?? '',
      environment: drawerFilters.environment ?? '',
      timeRange: drawerFilters.timeRange,
      startTimeAfter: drawerFilters.startTimeAfter ?? '',
      startTimeBefore: drawerFilters.startTimeBefore ?? '',
      traceSource: drawerFilters.traceSource ?? '',
      traceMetricsStatus: drawerFilters.traceMetricsStatus ?? '',
      providers: drawerFilters.providers ?? [],
      testRunId: drawerFilters.testRunId ?? '',
      testResultId: drawerFilters.testResultId ?? '',
      testId: drawerFilters.testId ?? '',
      traceType: drawerFilters.traceType ?? '',
    }),
    [searchQuery, drawerFilters]
  );
  const spanFilters = useMemo(
    () => spansListFilters(drawerFilters, searchQuery),
    [searchQuery, drawerFilters]
  );

  const listEnabled = !projectLoading && !!scopedProjectId;
  const onListError = useCallback(() => setErrorDismissed(false), []);

  const traces = useList(tracesDescriptor, {
    filters: traceFilters,
    enabled: listEnabled && view === 'traces',
    initialData,
    initialTotalCount,
    onError: onListError,
  });
  const spans = useList(spansDescriptor, {
    filters: spanFilters,
    enabled: listEnabled && view === 'spans',
    onError: onListError,
  });
  const active = view === 'spans' ? spans : traces;
  const { totalCount, refresh } = active;
  const rawError = active.error;

  useEffect(() => {
    setErrorDismissed(false);
  }, [rawError]);

  const error = rawError && !errorDismissed ? rawError : null;
  const dismissError = useCallback(() => setErrorDismissed(true), []);

  // Compare against the last seen value, not a "first run" flag: Strict Mode's
  // double-invoked mount effect would consume the flag and refetch on mount.
  const lastRefreshTrigger = useRef(refreshTrigger);
  useEffect(() => {
    if (lastRefreshTrigger.current === refreshTrigger) return;
    lastRefreshTrigger.current = refreshTrigger;
    refresh();
    // Only refreshTrigger (bumped by the wrapper's refresh FAB) should re-run this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  const listLoading = active.isLoading || projectLoading;

  const filterScope = useMemo(
    () => ({
      testRunScope: Boolean(fixedTestRunId),
      excludeTestRunId: Boolean(fixedTestRunId),
      view,
    }),
    [fixedTestRunId, view]
  );
  const hasActiveDrawerFilters = hasActiveTraceDrawerFilters(
    drawerFilters,
    filterScope
  );
  const activeFilterCount = countActiveTraceDrawerFilters(
    drawerFilters,
    filterScope
  );

  useEffect(() => {
    const unfiltered = !searchQuery.trim() && !hasActiveDrawerFilters;
    onUnfilteredEmpty?.(
      !listLoading && !!scopedProjectId && totalCount === 0 && unfiltered
    );
  }, [
    listLoading,
    scopedProjectId,
    totalCount,
    searchQuery,
    hasActiveDrawerFilters,
    onUnfilteredEmpty,
  ]);

  const openDrawer = (
    traceId: string,
    projectId: string,
    spanId: string | null
  ) => {
    setSelectedTraceId(traceId);
    setSelectedProjectId(projectId);
    setSelectedSpanId(spanId);
    setDrawerOpen(true);
  };

  const handleTraceRowClick = (traceId: string, projectId: string) =>
    openDrawer(traceId, projectId, null);

  const handleSpanRowClick = (span: SpanSummary) =>
    openDrawer(span.trace_id, span.project_id, span.span_id);

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setSelectedTraceId(null);
    setSelectedProjectId(null);
    setSelectedSpanId(null);
    if (initialTraceId) {
      // Drop the deep link to the trace, keep the view and filters.
      const params = new URLSearchParams(window.location.search);
      params.delete('open_trace');
      params.delete('open_span');
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, {
        scroll: false,
      });
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

  const openFilterDrawer = useCallback(() => setFilterDrawerOpen(true), []);

  const toolbarState = useMemo(
    () => ({
      view,
      onViewChange: setView,
      searchQuery,
      setSearchQuery,
      openFilterDrawer,
      hasActiveDrawerFilters,
      activeFilterCount,
    }),
    [
      view,
      searchQuery,
      openFilterDrawer,
      hasActiveDrawerFilters,
      activeFilterCount,
    ]
  );

  const showFilteredEmpty =
    !listLoading && active.data.length === 0 && totalCount === 0;

  // GET /telemetry/metrics narrows by project, environment, time and test run, so
  // any other filter the shown table applies makes the rollup broader than the
  // listed rows. Tell it, rather than letting the two silently disagree.
  const rollupProjectId = drawerFilters.projectId || scopedProjectId;
  const rollupTestRunId =
    fixedTestRunId ?? drawerFilters.testRunId ?? undefined;
  const viewOnlyFilters =
    view === 'spans'
      ? drawerFilters.spanTypes?.length ||
        drawerFilters.spanNames?.length ||
        drawerFilters.isRoot !== undefined
      : drawerFilters.endpointId || drawerFilters.traceMetricsStatus;
  const hasUnsupportedRollupFilters = Boolean(
    searchQuery.trim() ||
    viewOnlyFilters ||
    drawerFilters.traceType ||
    drawerFilters.traceSource ||
    // The metrics endpoint has no provider filter, so the tiles above cover more
    // traces than the table lists and say so.
    drawerFilters.providers?.length ||
    drawerFilters.testResultId ||
    drawerFilters.testId
  );
  const rollupTimeParams = useMemo(
    () => buildTraceQueryParams(drawerFilters, ''),
    [drawerFilters]
  );

  return (
    <>
      {/* Totals sit above the grid card, not inside it. The metrics endpoint scopes
          by test run, so on a run's Traces tab these describe that run. */}
      <TraceMetricsSummary
        projectId={rollupProjectId}
        testRunId={rollupTestRunId}
        environment={drawerFilters.environment ?? undefined}
        startTimeAfter={rollupTimeParams.start_time_after}
        startTimeBefore={rollupTimeParams.start_time_before}
        hasUnsupportedFilters={hasUnsupportedRollupFilters}
        refreshTrigger={refreshTrigger}
      />

      <Paper sx={GRID_PAPER_SX}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={dismissError}>
            {error}
          </Alert>
        )}

        <TracesToolbarContext.Provider value={toolbarState}>
          {view === 'spans' ? (
            <SpansTable
              spans={spans.data}
              loading={listLoading}
              onRowClick={handleSpanRowClick}
              totalCount={spans.totalCount}
              page={spans.page}
              pageSize={spans.rowsPerPage}
              onPageChange={spans.onPageChange}
              onPageSizeChange={spans.onRowsPerPageChange}
              sortModel={spans.sortModel}
              onSortModelChange={spans.onSortModelChange}
            />
          ) : (
            <TracesTable
              traces={traces.data}
              loading={listLoading}
              onRowClick={handleTraceRowClick}
              totalCount={traces.totalCount}
              page={traces.page}
              pageSize={traces.rowsPerPage}
              onPageChange={traces.onPageChange}
              onPageSizeChange={traces.onRowsPerPageChange}
              sortModel={traces.sortModel}
              onSortModelChange={traces.onSortModelChange}
            />
          )}
        </TracesToolbarContext.Provider>

        {showFilteredEmpty && (
          <Box sx={{ py: 6, textAlign: 'center' }}>
            <Typography variant="h6" gutterBottom>
              {view === 'spans' ? 'No spans found' : 'No traces found'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Try adjusting your filters or check back after running tests or
              invoking endpoints.
            </Typography>
          </Box>
        )}
      </Paper>

      <TraceFilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        filters={drawerFilters}
        onApply={handleApplyDrawerFilters}
        fixedTestRunId={fixedTestRunId}
        view={view}
      />

      <TraceDrawer
        open={drawerOpen}
        onClose={handleCloseDrawer}
        traceId={selectedTraceId}
        projectId={selectedProjectId || ''}
        initialSpanId={selectedSpanId ?? undefined}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        currentUserPicture={currentUserPicture}
        onTraceUpdated={refresh}
      />
    </>
  );
}
