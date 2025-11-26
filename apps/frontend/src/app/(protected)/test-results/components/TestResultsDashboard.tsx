'use client';

import React, { useState, useCallback } from 'react';
import { Box, useTheme } from '@mui/material';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import TestResultsFilters from './TestResultsFilters';
import TestResultsCharts from './TestResultsCharts';

interface TestResultsDashboardProps {
  sessionToken: string;
}

export default function TestResultsDashboard({
  sessionToken,
}: TestResultsDashboardProps) {
  const theme = useTheme();
  const [filters, setFilters] = useState<Partial<TestResultsStatsOptions>>({
    months: 1,
  });

  const handleFiltersChange = useCallback(
    (newFilters: Partial<TestResultsStatsOptions>) => {
      setFilters(newFilters);
    },
    []
  );

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
      }}
    >
      {/* Filters */}
      <TestResultsFilters
        onFiltersChange={handleFiltersChange}
        initialFilters={filters}
        sessionToken={sessionToken}
      />

      {/* Charts - Each chart makes its own API call in parallel */}
      <TestResultsCharts sessionToken={sessionToken} filters={filters} />
    </Box>
  );
}
