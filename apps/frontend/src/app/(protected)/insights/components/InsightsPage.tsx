'use client';

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Box } from '@mui/material';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { PageLayout } from '@/components/layout/PageLayout';
import TestResultsFilters from './TestResultsFilters';
import BehaviorInsightsView from './BehaviorInsightsView';
import InsightsFailedTestsFab from './InsightsFailedTestsFab';
import {
  DEFAULT_INSIGHTS_FILTERS,
  normalizeInsightsFilters,
  InsightsFilters,
} from '../types';
import {
  resolveEndpointId,
  chunkBehaviorColumns,
  isBehaviorRowExpandable,
} from '../utils/behavior-insights-utils';
import { useBehaviorInsightsData } from '../hooks/useBehaviorInsightsData';

interface InsightsPageProps {
  sessionToken: string;
}

export default function InsightsPage({ sessionToken }: InsightsPageProps) {
  const { activeProject } = useActiveProject();
  const [filters, setFilters] = useState<InsightsFilters>(() =>
    normalizeInsightsFilters(DEFAULT_INSIGHTS_FILTERS)
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [endpointsLoading, setEndpointsLoading] = useState(true);

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
    loading: insightsLoading,
    error,
    noRuns,
  } = useBehaviorInsightsData(sessionToken, filters);

  const filteredColumns = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return columns;
    return columns.filter(column => column.name.toLowerCase().includes(query));
  }, [columns, searchQuery]);

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
  }, [filters.endpointId, filters.timeRange, expandableRowIndices]);

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
    if (!sessionToken) return;

    let mounted = true;

    const loadEndpoints = async () => {
      setEndpointsLoading(true);
      try {
        const client = new ApiClientFactory(sessionToken).getEndpointsClient();
        const response = await client.getEndpoints({
          limit: 100,
          sort_by: 'name',
          sort_order: 'asc',
        });
        if (mounted) setEndpoints(response.data);
      } catch {
        if (mounted) setEndpoints([]);
      } finally {
        if (mounted) setEndpointsLoading(false);
      }
    };

    void loadEndpoints();
    return () => {
      mounted = false;
    };
  }, [sessionToken]);

  useEffect(() => {
    if (endpointsLoading) return;

    if (projectEndpoints.length === 0) {
      setFilters(prev =>
        prev.endpointId === ''
          ? prev
          : { timeRange: prev.timeRange, endpointId: '' }
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
        : { timeRange: prev.timeRange, endpointId: resolvedId }
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

  const failedCount = summary?.failed ?? 0;
  const fabLoading = endpointsLoading || insightsLoading;

  return (
    <PageLayout
      title="Insights"
      description="View pass rates by behavior, metric, and topic for your selected endpoint. Filter by time range or switch endpoints to compare performance."
      breadcrumbs={[]}
      actions={
        <InsightsFailedTestsFab
          filters={filters}
          failedCount={failedCount}
          loading={fabLoading}
          disabled={projectEndpoints.length === 0}
        />
      }
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 0,
        }}
      >
        <TestResultsFilters
          filters={filters}
          onFiltersChange={handleFiltersChange}
          projectEndpoints={projectEndpoints}
          endpointsLoading={endpointsLoading}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
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
            columns,
            loading: insightsLoading,
            error,
            noRuns,
          }}
          searchQuery={searchQuery}
          endpointName={selectedEndpointName}
          endpointsLoading={endpointsLoading}
          noEndpoints={!endpointsLoading && projectEndpoints.length === 0}
          columnRows={columnRows}
          expandedRows={expandedRows}
          onRowToggle={handleRowToggle}
        />
      </Box>
    </PageLayout>
  );
}
