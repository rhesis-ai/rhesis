'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { Box } from '@mui/material';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import TestResultsFilters from './TestResultsFilters';
import BehaviorInsightsView from './BehaviorInsightsView';
import { DEFAULT_INSIGHTS_FILTERS, InsightsFilters } from '../types';

interface InsightsPageProps {
  sessionToken: string;
}

export default function InsightsPage({ sessionToken }: InsightsPageProps) {
  const { activeProject } = useActiveProject();
  const [filters, setFilters] = useState<InsightsFilters>(
    DEFAULT_INSIGHTS_FILTERS
  );
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [endpointsLoading, setEndpointsLoading] = useState(true);

  const handleFiltersChange = useCallback((newFilters: InsightsFilters) => {
    setFilters(newFilters);
  }, []);

  const handleEndpointsLoaded = useCallback((loaded: Endpoint[]) => {
    setEndpoints(loaded);
    setEndpointsLoading(false);
  }, []);

  const projectEndpoints = useMemo(
    () =>
      activeProject
        ? endpoints.filter(e => e.project_id === activeProject.id)
        : endpoints,
    [endpoints, activeProject]
  );

  const selectedEndpointName = useMemo(
    () => projectEndpoints.find(e => e.id === filters.endpointId)?.name,
    [projectEndpoints, filters.endpointId]
  );

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
      }}
    >
      <TestResultsFilters
        onFiltersChange={handleFiltersChange}
        onEndpointsLoaded={handleEndpointsLoaded}
        sessionToken={sessionToken}
      />

      <BehaviorInsightsView
        sessionToken={sessionToken}
        filters={filters}
        endpointName={selectedEndpointName}
        endpointsLoading={endpointsLoading}
        noEndpoints={!endpointsLoading && projectEndpoints.length === 0}
      />
    </Box>
  );
}
