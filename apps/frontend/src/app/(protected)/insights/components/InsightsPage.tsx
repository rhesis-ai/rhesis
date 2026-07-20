'use client';

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Alert, Box, Button, CircularProgress } from '@mui/material';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { useEndpoints } from '@/hooks/useEndpoints';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { PageLayout } from '@/components/layout/PageLayout';
import TestResultsFilters from './TestResultsFilters';
import BehaviorInsightsView from './BehaviorInsightsView';
import InsightsFailedTestsFab from './InsightsFailedTestsFab';
import InsightsSummarizeFab from './InsightsSummarizeFab';
import { FabGroup } from '@/components/common/Fab';
import {
  DEFAULT_INSIGHTS_FILTERS,
  DEFAULT_INSIGHTS_TIME_RANGE,
  normalizeInsightsFilters,
  InsightsFilters,
} from '../types';
import {
  resolveEndpointId,
  chunkBehaviorColumns,
  isBehaviorRowExpandable,
} from '../utils/behavior-insights-utils';
import {
  filterColumnsByBehaviorIds,
  InsightsBehaviorOption,
} from '../utils/insights-filter-utils';
import { useBehaviorInsightsData } from '../hooks/useBehaviorInsightsData';
import InsightsEmptyState from './InsightsEmptyState';
import { resolveInsightsPageView } from '../utils/insights-page-view';

interface InsightsPageProps {
  sessionToken: string;
}

export default function InsightsPage({ sessionToken }: InsightsPageProps) {
  const { activeProject } = useActiveProject();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.TestResult.READ
  );
  const [filters, setFilters] = useState<InsightsFilters>(() =>
    normalizeInsightsFilters(DEFAULT_INSIGHTS_FILTERS)
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const {
    data: endpoints = [],
    isLoading: endpointsLoading,
    isError: endpointsHasError,
    refetch: refetchEndpoints,
  } = useEndpoints(
    sessionToken,
    {
      limit: 100,
      sort_by: 'name',
      sort_order: 'asc',
    },
    !permsLoading && canRead
  );
  const endpointsError = endpointsHasError
    ? 'Failed to load endpoints. Please try again.'
    : null;

  const projectEndpoints = useMemo(
    () =>
      activeProject
        ? endpoints.filter(
            e => String(e.project_id) === String(activeProject.id)
          )
        : endpoints,
    [endpoints, activeProject]
  );

  const {
    summary,
    columns,
    failedTestCaseCount,
    loading: insightsLoading,
    error,
    noRuns,
  } = useBehaviorInsightsData(sessionToken, filters, !permsLoading && canRead);

  const behaviorOptions = useMemo<InsightsBehaviorOption[]>(
    () =>
      columns.map(column => ({
        id: column.id,
        name: column.name,
        count: column.overall.total,
      })),
    [columns]
  );

  const behaviorFilteredColumns = useMemo(
    () => filterColumnsByBehaviorIds(columns, filters.behaviorIds),
    [columns, filters.behaviorIds]
  );

  const filteredColumns = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return behaviorFilteredColumns;
    return behaviorFilteredColumns.filter(column =>
      column.name.toLowerCase().includes(query)
    );
  }, [behaviorFilteredColumns, searchQuery]);

  const columnRows = useMemo(
    () => chunkBehaviorColumns(filteredColumns),
    [filteredColumns]
  );

  const expandableRowIndices = useMemo(
    () =>
      columnRows.flatMap((row, index) =>
        isBehaviorRowExpandable(row) ? [index] : []
      ),
    [columnRows]
  );

  useEffect(() => {
    setExpandedRows(new Set(expandableRowIndices));
  }, [
    filters.endpointId,
    filters.runFilterMode,
    filters.timeRange,
    filters.testRunIds,
    filters.behaviorIds,
    expandableRowIndices,
  ]);

  const allExpanded =
    expandableRowIndices.length > 0 &&
    expandableRowIndices.every(index => expandedRows.has(index));

  const handleToggleAll = useCallback(() => {
    setExpandedRows(allExpanded ? new Set() : new Set(expandableRowIndices));
  }, [allExpanded, expandableRowIndices]);

  const handleRowToggle = useCallback((rowIndex: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(rowIndex)) next.delete(rowIndex);
      else next.add(rowIndex);
      return next;
    });
  }, []);

  useEffect(() => {
    if (endpointsLoading) return;

    if (projectEndpoints.length === 0) {
      setFilters(prev =>
        prev.endpointId === '' ? prev : { ...prev, endpointId: '' }
      );
      return;
    }

    const projectId = activeProject?.id ? String(activeProject.id) : undefined;
    const hasValidSelection = projectEndpoints.some(
      e => e.id === filters.endpointId
    );
    if (hasValidSelection) return;

    const resolvedId = resolveEndpointId(endpoints, projectId);
    if (!resolvedId) return;

    setFilters(prev =>
      prev.endpointId === resolvedId
        ? prev
        : {
            ...prev,
            endpointId: resolvedId,
            testRunIds: [],
            runFilterMode: 'timeRange',
            timeRange: DEFAULT_INSIGHTS_TIME_RANGE,
          }
    );
  }, [
    endpointsLoading,
    endpoints,
    activeProject?.id,
    projectEndpoints,
    filters.endpointId,
  ]);

  const handleFiltersChange = useCallback((newFilters: InsightsFilters) => {
    setFilters(normalizeInsightsFilters(newFilters));
  }, []);

  const selectedEndpointName = useMemo(
    () => projectEndpoints.find(e => e.id === filters.endpointId)?.name,
    [projectEndpoints, filters.endpointId]
  );

  const visibleBehaviorNames = useMemo(
    () => filteredColumns.map(column => column.name),
    [filteredColumns]
  );

  const fabLoading =
    endpointsLoading ||
    insightsLoading ||
    (failedTestCaseCount === null && (summary?.failed ?? 0) > 0);

  const pageView = resolveInsightsPageView({
    endpointsLoading,
    endpointsError,
    projectEndpointCount: projectEndpoints.length,
    endpointId: filters.endpointId,
    insightsLoading,
    error,
    noRuns,
  });

  const filterBarProps = {
    filters,
    onFiltersChange: handleFiltersChange,
    sessionToken,
    projectEndpoints,
    endpointsLoading,
    behaviorOptions,
    searchQuery,
    onSearchChange: setSearchQuery,
  } as const;

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="insights" />;

  return (
    <PageLayout
      title="Insights"
      description="View pass rates by behavior, metric, and topic. Filter by time range or pick specific test runs in the filter drawer."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <InsightsSummarizeFab
            sessionToken={sessionToken}
            filters={filters}
            endpointName={selectedEndpointName}
            visibleBehaviorNames={visibleBehaviorNames}
            loading={fabLoading}
            disabled={projectEndpoints.length === 0}
          />
          <InsightsFailedTestsFab
            filters={filters}
            failedCount={failedTestCaseCount ?? 0}
            loading={fabLoading}
            disabled={projectEndpoints.length === 0}
          />
        </FabGroup>
      }
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 0,
        }}
      >
        {pageView === 'loading-endpoints' ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
            <CircularProgress />
          </Box>
        ) : pageView === 'endpoints-error' ? (
          <Box sx={{ mt: 2 }}>
            <Alert
              severity="error"
              action={
                <Button
                  color="inherit"
                  size="small"
                  onClick={() => refetchEndpoints()}
                >
                  Retry
                </Button>
              }
            >
              {endpointsError}
            </Alert>
          </Box>
        ) : pageView === 'empty-no-endpoints' ? (
          <InsightsEmptyState variant="no-endpoints" />
        ) : pageView === 'empty-no-test-results' ? (
          <>
            <TestResultsFilters {...filterBarProps} variant="compact" />
            <InsightsEmptyState variant="no-test-results" />
          </>
        ) : (
          <>
            <TestResultsFilters
              {...filterBarProps}
              showExpandToggle={
                !fabLoading &&
                expandableRowIndices.length > 0 &&
                projectEndpoints.length > 0
              }
              allExpanded={allExpanded}
              onToggleAll={handleToggleAll}
            />

            <BehaviorInsightsView
              sessionToken={sessionToken}
              filters={filters}
              insights={{
                summary,
                columns: filteredColumns,
                failedTestCaseCount,
                loading: insightsLoading,
                error,
                noRuns,
              }}
              searchQuery={searchQuery}
              endpointName={selectedEndpointName}
              endpointsLoading={endpointsLoading}
              columnRows={columnRows}
              expandedRows={expandedRows}
              onRowToggle={handleRowToggle}
            />
          </>
        )}
      </Box>
    </PageLayout>
  );
}
