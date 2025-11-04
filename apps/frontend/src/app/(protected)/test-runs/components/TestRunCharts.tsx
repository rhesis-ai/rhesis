'use client';

import React, { useEffect, useState, useRef } from 'react';
import { BasePieChart, BaseChartsGrid } from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TestRunStatsStatus,
  TestRunStatsResults,
  TestRunStatsTests,
  TestRunStatsExecutors,
} from '@/utils/api-client/interfaces/test-run-stats';
import { Box, CircularProgress, Typography, Paper } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

// Fallback mock data in case the API fails
const fallbackData = [{ name: 'Loading...', value: 100 }];

// Configuration for each chart
const CHART_CONFIG = {
  status: { top: 5, title: 'Test Runs by Status' },
  result: { top: 5, title: 'Test Runs by Result' },
  test: { top: 5, title: 'Most Run Test Sets' },
  executor: { top: 5, title: 'Top Test Executors' },
};

// Helper function to truncate long names for legends
const truncateName = (name: string): string => {
  if (name.length <= 15) return name;
  return `${name.substring(0, 12)}...`;
};

// Using real API interfaces now

interface TestRunChartsProps {
  sessionToken: string;
  totalCount?: number;
}

export default function TestRunCharts({
  sessionToken,
  totalCount = 0,
}: TestRunChartsProps) {
  const isMounted = useRef(false);

  // Global loading state for all charts
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Individual state for each chart (simplified - no individual loading/error states)
  const [statusChart, setStatusChart] = useState<TestRunStatsStatus | null>(
    null
  );
  const [resultChart, setResultChart] = useState<TestRunStatsResults | null>(
    null
  );
  const [testChart, setTestChart] = useState<TestRunStatsTests | null>(null);
  const [executorChart, setExecutorChart] =
    useState<TestRunStatsExecutors | null>(null);

  useEffect(() => {
    isMounted.current = true;

    const fetchAllCharts = async () => {
      if (!sessionToken) return;

      try {
        setIsLoading(true);
        setHasError(false);
        setErrorMessage(null);

        const clientFactory = new ApiClientFactory(sessionToken);
        const testRunsClient = clientFactory.getTestRunsClient();

        // Fetch all chart data in parallel
        const [statusStats, resultStats, testStats, executorStats] =
          await Promise.all([
            testRunsClient.getTestRunStats({
              mode: 'status',
              top: 5,
              months: 6,
            }),
            testRunsClient.getTestRunStats({
              mode: 'results',
              top: 5,
              months: 6,
            }),
            testRunsClient.getTestRunStats({
              mode: 'test_sets',
              top: 5,
              months: 6,
            }),
            testRunsClient.getTestRunStats({
              mode: 'executors',
              top: 5,
              months: 6,
            }),
          ]);

        if (isMounted.current) {
          setStatusChart(statusStats as TestRunStatsStatus);
          setResultChart(resultStats as TestRunStatsResults);
          setTestChart(testStats as TestRunStatsTests);
          setExecutorChart(executorStats as TestRunStatsExecutors);
          setIsLoading(false);
        }
      } catch (err) {
        if (isMounted.current) {
          setIsLoading(false);
          setHasError(true);
          setErrorMessage('Failed to load chart data');
        }
      }
    };

    fetchAllCharts();

    return () => {
      isMounted.current = false;
    };
  }, [sessionToken]);

  // Generate chart data from individual chart states
  const generateStatusData = () => {
    if (!statusChart) return fallbackData;

    return statusChart.status_distribution
      .slice(0, CHART_CONFIG.status.top)
      .map(item => ({
        name: truncateName(item.status),
        value: item.count,
        fullName: item.status,
      }));
  };

  const generateResultData = () => {
    if (!resultChart) return fallbackData;

    const { result_distribution } = resultChart;
    return [
      { name: 'Passed', value: result_distribution.passed, fullName: 'Passed' },
      { name: 'Failed', value: result_distribution.failed, fullName: 'Failed' },
      {
        name: 'Pending',
        value: result_distribution.pending,
        fullName: 'Pending',
      },
    ].filter(item => item.value > 0); // Only show categories with data
  };

  const generateTestData = () => {
    if (!testChart) return fallbackData;

    return testChart.most_run_test_sets
      .slice(0, CHART_CONFIG.test.top)
      .map(item => ({
        name: truncateName(item.test_set_name),
        value: item.run_count,
        fullName: item.test_set_name,
      }));
  };

  const generateExecutorData = () => {
    if (!executorChart) return fallbackData;

    return executorChart.top_executors
      .slice(0, CHART_CONFIG.executor.top)
      .map(item => ({
        name: truncateName(item.executor_name),
        value: item.run_count,
        fullName: item.executor_name,
      }));
  };

  // Show single loading spinner for all charts (matching test-sets style)
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show error state for all charts (matching test-sets style)
  if (hasError) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="error">
          {errorMessage || 'Failed to load chart data'}
        </Typography>
      </Box>
    );
  }

  // Show empty state when no test runs exist
  if (totalCount === 0) {
    return (
      <Paper
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
        }}
      >
        <InfoOutlinedIcon color="info" />
        <Typography color="text.secondary">
          No test runs yet. Create your first test run to get started.
        </Typography>
      </Paper>
    );
  }

  // Show all charts when loaded
  return (
    <BaseChartsGrid>
      <BasePieChart
        title={CHART_CONFIG.status.title}
        data={generateStatusData()}
        useThemeColors={true}
        colorPalette="pie"
      />

      <BasePieChart
        title={CHART_CONFIG.result.title}
        data={generateResultData()}
        useThemeColors={true}
        colorPalette="pie"
      />

      <BasePieChart
        title={CHART_CONFIG.test.title}
        data={generateTestData()}
        useThemeColors={true}
        colorPalette="pie"
      />

      <BasePieChart
        title={CHART_CONFIG.executor.title}
        data={generateExecutorData()}
        useThemeColors={true}
        colorPalette="pie"
      />
    </BaseChartsGrid>
  );
}
