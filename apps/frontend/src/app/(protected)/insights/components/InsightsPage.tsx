'use client';

import React, { useState, useCallback } from 'react';
import { Box } from '@mui/material';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import TestResultsFilters from './TestResultsFilters';
import TestResultsCharts from './TestResultsCharts';

interface InsightsPageProps {
  sessionToken: string;
}

export default function InsightsPage({ sessionToken }: InsightsPageProps) {
  const [filters, setFilters] = useState<Partial<TestResultsStatsOptions>>({
    months: 1,
  });
  const [searchValue, setSearchValue] = useState('');

  const handleFiltersChange = useCallback(
    (newFilters: Partial<TestResultsStatsOptions>) => {
      setFilters(newFilters);
    },
    []
  );

  const handleSearchChange = useCallback((value: string) => {
    setSearchValue(value);
  }, []);

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
        onSearchChange={handleSearchChange}
        initialFilters={filters}
        sessionToken={sessionToken}
        searchPlaceholder="Search runs on Overview..."
      />

      <TestResultsCharts
        sessionToken={sessionToken}
        filters={filters}
        searchValue={searchValue}
      />
    </Box>
  );
}
