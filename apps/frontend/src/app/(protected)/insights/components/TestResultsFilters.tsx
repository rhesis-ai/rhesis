'use client';

import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  ToggleButtonGroup,
  ToggleButton,
  Button,
  useTheme,
} from '@mui/material';
import { Clear as ClearIcon } from '@mui/icons-material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Endpoint } from '@/utils/api-client/interfaces/endpoint';
import { useActiveProject } from '@/contexts/ActiveProjectContext';
import { resolveEndpointId } from '../utils/behavior-insights-utils';
import { writeInsightsEndpointId } from '@/utils/insights-endpoint';
import { DEFAULT_INSIGHTS_FILTERS, InsightsFilters } from '../types';

interface TestResultsFiltersProps {
  onFiltersChange: (filters: InsightsFilters) => void;
  onEndpointsLoaded?: (endpoints: Endpoint[]) => void;
  sessionToken: string;
}

const TIME_RANGES = [
  { value: 1, label: '1M' },
  { value: 3, label: '3M' },
  { value: 6, label: '6M' },
  { value: 12, label: '1Y' },
];

export default function TestResultsFilters({
  onFiltersChange,
  onEndpointsLoaded,
  sessionToken,
}: TestResultsFiltersProps) {
  const theme = useTheme();
  const { activeProject } = useActiveProject();
  const [filters, setFilters] = useState<InsightsFilters>(
    DEFAULT_INSIGHTS_FILTERS
  );
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [isLoadingEndpoints, setIsLoadingEndpoints] = useState(false);

  const projectEndpoints = activeProject
    ? endpoints.filter(e => e.project_id === activeProject.id)
    : endpoints;

  const loadEndpoints = useCallback(async () => {
    if (!sessionToken) return;

    try {
      setIsLoadingEndpoints(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const endpointsClient = clientFactory.getEndpointsClient();

      const response = await endpointsClient.getEndpoints({
        limit: 100,
        sort_by: 'name',
        sort_order: 'asc',
      });
      setEndpoints(response.data);
      onEndpointsLoaded?.(response.data);
    } catch (_error) {
      setEndpoints([]);
      onEndpointsLoaded?.([]);
    } finally {
      setIsLoadingEndpoints(false);
    }
  }, [sessionToken, onEndpointsLoaded]);

  useEffect(() => {
    void loadEndpoints();
  }, [loadEndpoints]);

  useEffect(() => {
    if (isLoadingEndpoints) return;

    if (projectEndpoints.length === 0) {
      setFilters(prev => {
        const cleared: InsightsFilters = {
          months: prev.months,
          endpointId: '',
        };
        onFiltersChange(cleared);
        return cleared;
      });
      return;
    }

    const resolvedId = resolveEndpointId(
      endpoints,
      activeProject?.id ? String(activeProject.id) : undefined
    );

    if (!resolvedId) return;

    setFilters(prev => {
      if (prev.endpointId === resolvedId) return prev;
      const next: InsightsFilters = {
        months: prev.months,
        endpointId: resolvedId,
      };
      onFiltersChange(next);
      return next;
    });
  }, [
    isLoadingEndpoints,
    endpoints,
    activeProject?.id,
    projectEndpoints.length,
    onFiltersChange,
  ]);

  const updateFilters = useCallback(
    (patch: Partial<InsightsFilters>) => {
      setFilters(prev => {
        const next = { ...prev, ...patch };
        onFiltersChange(next);
        return next;
      });
    },
    [onFiltersChange]
  );

  const handleTimeRangeChange = (months: number) => {
    updateFilters({ months });
  };

  const handleEndpointChange = (endpointId: string) => {
    writeInsightsEndpointId(endpointId);
    updateFilters({ endpointId });
  };

  const resetTime = () => {
    updateFilters({ months: DEFAULT_INSIGHTS_FILTERS.months });
  };

  const hasNonDefaultTime = filters.months !== DEFAULT_INSIGHTS_FILTERS.months;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        gap: 2,
        alignItems: { xs: 'stretch', md: 'center' },
        justifyContent: 'space-between',
        flexWrap: 'wrap',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          gap: 2,
          flex: 1,
          alignItems: { xs: 'stretch', sm: 'center' },
          flexWrap: 'wrap',
        }}
      >
        <ToggleButtonGroup
          value={filters.months}
          exclusive
          onChange={(_, value) => value && handleTimeRangeChange(value)}
          size="small"
          sx={{
            '& .MuiToggleButton-root': {
              px: 2,
              py: 0.5,
              textTransform: 'none',
              fontWeight: 500,
            },
            '& .MuiToggleButton-root.Mui-selected': {
              backgroundColor: theme.palette.primary.main,
              color: theme.palette.primary.contrastText,
              '&:hover': {
                backgroundColor: theme.palette.primary.dark,
              },
            },
          }}
        >
          {TIME_RANGES.map(range => (
            <ToggleButton key={range.value} value={range.value}>
              {range.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>

        <FormControl
          sx={{ minWidth: { xs: '100%', sm: 280 } }}
          size="small"
          disabled={isLoadingEndpoints || projectEndpoints.length === 0}
        >
          <InputLabel id="insights-endpoint-label">Endpoint</InputLabel>
          <Select
            labelId="insights-endpoint-label"
            value={filters.endpointId || ''}
            label="Endpoint"
            onChange={e => handleEndpointChange(e.target.value)}
          >
            {projectEndpoints.map(endpoint => (
              <MenuItem key={endpoint.id} value={endpoint.id}>
                {endpoint.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      {hasNonDefaultTime && (
        <Button
          variant="outlined"
          size="small"
          startIcon={<ClearIcon />}
          onClick={resetTime}
          sx={{
            whiteSpace: 'nowrap',
            alignSelf: { xs: 'flex-start', md: 'center' },
          }}
        >
          Reset time
        </Button>
      )}
    </Box>
  );
}
