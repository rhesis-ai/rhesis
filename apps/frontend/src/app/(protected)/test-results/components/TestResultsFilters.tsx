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
  TextField,
  InputAdornment,
  Typography,
  useTheme,
} from '@mui/material';
import { Clear as ClearIcon, Search as SearchIcon } from '@mui/icons-material';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSet } from '@/utils/api-client/interfaces/test-set';

interface TestResultsFiltersProps {
  onFiltersChange: (filters: Partial<TestResultsStatsOptions>) => void;
  initialFilters?: Partial<TestResultsStatsOptions>;
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
  initialFilters = {},
  sessionToken,
}: TestResultsFiltersProps) {
  const theme = useTheme();
  const [filters, setFilters] =
    useState<Partial<TestResultsStatsOptions>>(initialFilters);
  const [testSets, setTestSets] = useState<TestSet[]>([]);
  const [isLoadingTestSets, setIsLoadingTestSets] = useState(false);
  const [searchValue, setSearchValue] = useState('');

  const updateFilters = useCallback(
    (newFilters: Partial<TestResultsStatsOptions>) => {
      const updatedFilters = { ...filters, ...newFilters };
      setFilters(updatedFilters);
      onFiltersChange(updatedFilters);
    },
    [filters, onFiltersChange]
  );

  // Load test sets
  const loadTestSets = useCallback(async () => {
    if (!sessionToken) return;

    try {
      setIsLoadingTestSets(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testSetsClient = clientFactory.getTestSetsClient();

      const response = await testSetsClient.getTestSets({
        limit: 100,
        has_runs: true,
        sort_by: 'created_at',
        sort_order: 'desc', // Sort by most recent first
      });
      setTestSets(response.data);
    } catch (error) {
    } finally {
      setIsLoadingTestSets(false);
    }
  }, [sessionToken]);

  // Effect to load test sets on mount
  useEffect(() => {
    loadTestSets();
  }, [loadTestSets]);

  const handleTimeRangeChange = (months: number) => {
    updateFilters({ months, start_date: undefined, end_date: undefined });
  };

  const handleTestSetChange = (testSetId: string) => {
    const newFilters: Partial<TestResultsStatsOptions> = {
      test_set_ids: testSetId ? [testSetId] : undefined,
    };
    updateFilters(newFilters);
  };

  const handleSearchChange = (value: string) => {
    setSearchValue(value);
  };

  const clearFilters = () => {
    const clearedFilters: Partial<TestResultsStatsOptions> = { months: 1 };
    setFilters(clearedFilters);
    onFiltersChange(clearedFilters);
    setSearchValue('');
  };

  const hasActiveFilters =
    searchValue.length > 0 ||
    Object.keys(filters).some(
      key =>
        key !== 'months' &&
        filters[key as keyof TestResultsStatsOptions] !== undefined
    );

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
        }}
      >
        {/* Filter Controls */}
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
          {/* Left side: Filters */}
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
            {/* Search Field */}
            <TextField
              size="small"
              placeholder="Search test results..."
              value={searchValue}
              onChange={e => handleSearchChange(e.target.value)}
              variant="outlined"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ minWidth: { xs: '100%', sm: 250 } }}
            />

            {/* Time Range */}
            <ToggleButtonGroup
              value={filters.months || 1}
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

            {/* Test Set Filter */}
            <FormControl
              sx={{ minWidth: { xs: '100%', sm: 300, lg: 500 } }}
              size="small"
            >
              <InputLabel>Test Set</InputLabel>
              <Select
                value={filters.test_set_ids?.[0] || ''}
                label="Test Set"
                onChange={e => handleTestSetChange(e.target.value)}
                disabled={isLoadingTestSets}
              >
                <MenuItem value="">All Test Sets</MenuItem>
                {testSets.map(testSet => {
                  const testCount =
                    testSet.attributes?.metadata?.total_tests || 0;
                  return (
                    <MenuItem key={testSet.id} value={testSet.id}>
                      <Box
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          width: '100%',
                          gap: 2,
                        }}
                      >
                        <span>{testSet.name}</span>
                        {testCount > 0 && (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ ml: 'auto', flexShrink: 0 }}
                          >
                            {testCount} tests
                          </Typography>
                        )}
                      </Box>
                    </MenuItem>
                  );
                })}
              </Select>
            </FormControl>
          </Box>

          {/* Right side: Reset Button */}
          {hasActiveFilters && (
            <Box
              sx={{
                display: 'flex',
                gap: 1,
                flexShrink: 0,
                alignItems: 'center',
              }}
            >
              <Button
                variant="outlined"
                size="small"
                startIcon={<ClearIcon />}
                onClick={clearFilters}
                sx={{ whiteSpace: 'nowrap' }}
              >
                Reset
              </Button>
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
}
