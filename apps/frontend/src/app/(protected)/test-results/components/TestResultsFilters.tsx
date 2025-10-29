'use client';

import React, { useState, useCallback, useEffect } from 'react';
import {
  Paper,
  Box,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Button,
  IconButton,
  Chip,
  useTheme,
} from '@mui/material';
import { FilterList, Clear } from '@mui/icons-material';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSet } from '@/utils/api-client/interfaces/test-set';
import { TestRunDetail } from '@/utils/api-client/interfaces/test-run';

interface TestResultsFiltersProps {
  onFiltersChange: (filters: Partial<TestResultsStatsOptions>) => void;
  initialFilters?: Partial<TestResultsStatsOptions>;
  sessionToken: string;
}

const TIME_RANGES = [
  { value: 1, label: 'Last Month' },
  { value: 3, label: 'Last 3 Months' },
  { value: 6, label: 'Last 6 Months' },
  { value: 12, label: 'Last Year' },
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
  const [testRuns, setTestRuns] = useState<TestRunDetail[]>([]);
  const [isLoadingTestSets, setIsLoadingTestSets] = useState(false);
  const [isLoadingTestRuns, setIsLoadingTestRuns] = useState(false);

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
      });
      setTestSets(response.data);
    } catch (error) {
    } finally {
      setIsLoadingTestSets(false);
    }
  }, [sessionToken]);

  // Load test runs, optionally filtered by test set
  const loadTestRuns = useCallback(
    async (testSetId?: string) => {
      if (!sessionToken) return;

      try {
        setIsLoadingTestRuns(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const testRunsClient = clientFactory.getTestRunsClient();

        // Build filter for test runs based on test set if provided
        let filter = '';
        if (testSetId) {
          filter = `test_configuration/test_set/id eq '${testSetId}'`;
        }

        const response = await testRunsClient.getTestRuns({
          limit: 100,
          filter: filter || undefined,
        });
        setTestRuns(response.data);
      } catch (error) {
      } finally {
        setIsLoadingTestRuns(false);
      }
    },
    [sessionToken]
  );

  // Effect to load test sets on mount
  useEffect(() => {
    loadTestSets();
  }, [loadTestSets]);

  // Effect to reload test runs when test set filter changes
  useEffect(() => {
    const selectedTestSetId = filters.test_set_ids?.[0];
    loadTestRuns(selectedTestSetId);
  }, [filters.test_set_ids, loadTestRuns]);

  const handleTimeRangeChange = (months: number) => {
    updateFilters({ months, start_date: undefined, end_date: undefined });
  };

  const handleTestSetChange = (testSetId: string) => {
    const newFilters: Partial<TestResultsStatsOptions> = {
      test_set_ids: testSetId ? [testSetId] : undefined,
      test_run_ids: undefined, // Clear test run filter when test set changes
    };
    updateFilters(newFilters);
  };

  const handleTestRunChange = (testRunId: string) => {
    const newFilters: Partial<TestResultsStatsOptions> = {
      test_run_ids: testRunId ? [testRunId] : undefined,
    };
    updateFilters(newFilters);
  };

  const clearFilters = () => {
    const clearedFilters: Partial<TestResultsStatsOptions> = { months: 6 };
    setFilters(clearedFilters);
    onFiltersChange(clearedFilters);
    setTestRuns([]); // Clear test runs when clearing all filters
    loadTestRuns(); // Reload all test runs
  };

  const hasActiveFilters = Object.keys(filters).some(
    key =>
      key !== 'months' &&
      filters[key as keyof TestResultsStatsOptions] !== undefined
  );

  return (
    <Paper
      elevation={theme.elevation.standard}
      sx={{ p: theme.customSpacing.container.medium }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: theme.customSpacing.section.small,
        }}
      >
        <Typography
          variant="h6"
          sx={{ display: 'flex', alignItems: 'center', gap: theme.spacing(1) }}
        >
          <FilterList />
          Filters
        </Typography>
        {hasActiveFilters && (
          <Button
            variant="outlined"
            size="small"
            onClick={clearFilters}
            startIcon={<Clear />}
          >
            Clear Filters
          </Button>
        )}
      </Box>

      <Grid container spacing={theme.customSpacing.container.medium}>
        {/* Time Range */}
        <Grid item xs={12} sm={6} md={3}>
          <FormControl fullWidth>
            <InputLabel>Time Range</InputLabel>
            <Select
              value={filters.months || 6}
              label="Time Range"
              onChange={e => handleTimeRangeChange(Number(e.target.value))}
            >
              {TIME_RANGES.map(range => (
                <MenuItem key={range.value} value={range.value}>
                  {range.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Test Set Filter - First in order, now populated */}
        <Grid item xs={12} sm={6} md={3}>
          <FormControl fullWidth>
            <InputLabel>Test Set</InputLabel>
            <Select
              value={filters.test_set_ids?.[0] || ''}
              label="Test Set"
              onChange={e => handleTestSetChange(e.target.value)}
              disabled={isLoadingTestSets}
            >
              <MenuItem value="">All Test Sets</MenuItem>
              {testSets.map(testSet => (
                <MenuItem key={testSet.id} value={testSet.id}>
                  {testSet.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        {/* Test Run Filter - Second in order, filtered by test set */}
        <Grid item xs={12} sm={6} md={3}>
          <FormControl fullWidth>
            <InputLabel>Test Run</InputLabel>
            <Select
              value={filters.test_run_ids?.[0] || ''}
              label="Test Run"
              onChange={e => handleTestRunChange(e.target.value)}
              disabled={
                isLoadingTestRuns ||
                Boolean(filters.test_set_ids?.[0] && testRuns.length === 0)
              }
            >
              <MenuItem value="">All Test Runs</MenuItem>
              {testRuns.map(testRun => (
                <MenuItem key={testRun.id} value={testRun.id}>
                  {testRun.name || `Test Run ${testRun.id.slice(0, 8)}`}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>
      </Grid>

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <Box
          sx={{
            mt: theme.customSpacing.section.small,
            display: 'flex',
            gap: theme.spacing(1),
            flexWrap: 'wrap',
          }}
        >
          <Typography variant="body2" color="text.secondary" sx={{ mr: 1 }}>
            Active filters:
          </Typography>
          {filters.test_set_ids?.[0] && (
            <Chip
              key="test_set"
              label={`Test Set: ${testSets.find(ts => ts.id === filters.test_set_ids?.[0])?.name || 'Unknown'}`}
              size="small"
              variant="outlined"
              onDelete={() =>
                updateFilters({
                  test_set_ids: undefined,
                  test_run_ids: undefined,
                })
              }
            />
          )}
          {filters.test_run_ids?.[0] && (
            <Chip
              key="test_run"
              label={`Test Run: ${testRuns.find(tr => tr.id === filters.test_run_ids?.[0])?.name || 'Unknown'}`}
              size="small"
              variant="outlined"
              onDelete={() => updateFilters({ test_run_ids: undefined })}
            />
          )}
          {Object.entries(filters).map(([key, value]) => {
            if (
              key === 'months' ||
              key === 'test_set_ids' ||
              key === 'test_run_ids' ||
              !value
            )
              return null;
            return (
              <Chip
                key={key}
                label={`${key}: ${Array.isArray(value) ? value.join(', ') : value}`}
                size="small"
                variant="outlined"
                onDelete={() => updateFilters({ [key]: undefined })}
              />
            );
          })}
        </Box>
      )}
    </Paper>
  );
}
