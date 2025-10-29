'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  BasePieChart,
  BaseLineChart,
  BaseChartsGrid,
} from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestStats } from '@/utils/api-client/interfaces/tests';
import { TestResultsStats } from '@/utils/api-client/interfaces/test-results';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import { useSession } from 'next-auth/react';
import { format, subMonths } from 'date-fns';
import {
  Box,
  CircularProgress,
  Typography,
  Alert,
  useTheme,
} from '@mui/material';
import { chartUtils } from '@/components/common/BaseLineChart';
import { pieChartUtils } from '@/components/common/BasePieChart';
import { formatTimelineDate } from '@/app/(protected)/test-results/components/timelineUtils';

// Get last 6 months dynamically
const getLastSixMonths = () => chartUtils.getLastNMonths(6);

// Dynamically generated mock data for the last 6 months
const testTrendData = getLastSixMonths();

// Default data for dimension charts with non-zero values to ensure visualization
const dimensionDataBehavior = [
  { name: 'Reliability', value: 1 },
  { name: 'Robustness', value: 1 },
  { name: 'Compliance', value: 1 },
];

const dimensionDataCategory = [
  { name: 'Harmful', value: 1 },
  { name: 'Harmless', value: 1 },
  { name: 'Jailbreak', value: 1 },
];

// Fallback data for test cases managed - will be populated dynamically
const testCasesManagedData = getLastSixMonths();

// Types for chart data items
interface ChartDataItem {
  name: string;
  value: number;
  fullName?: string;
  percentage?: string;
}

export default function DashboardCharts() {
  const { data: session } = useSession();
  const theme = useTheme();
  const [testStats, setTestStats] = useState<TestStats | null>(null);
  const [testResultsStats, setTestResultsStats] =
    useState<TestResultsStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Use memoized session token to prevent unnecessary re-renders from session object recreation
  const sessionToken = React.useMemo(
    () => session?.session_token,
    [session?.session_token]
  );

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setIsLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken || '');

        // Fetch both test stats and test results timeline data in parallel
        const [testStatsResponse, testResultsResponse] = await Promise.all([
          clientFactory.getTestsClient().getTestStats({ top: 5, months: 6 }),
          clientFactory
            .getTestResultsClient()
            .getComprehensiveTestResultsStats({
              mode: 'timeline',
              months: 6,
            } as TestResultsStatsOptions),
        ]);

        setTestStats(testStatsResponse);
        setTestResultsStats(testResultsResponse);
        setError(null);
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to load statistics';
        setError(errorMessage);
      } finally {
        setIsLoading(false);
      }
    };

    if (sessionToken) {
      fetchStats();
    }
  }, [sessionToken]);

  // Create useCallback versions of the generator functions
  const generateCategoryDataCallback = useCallback(() => {
    // Define the function inside the callback to avoid recreation on every render
    const generateData = () => {
      if (!testStats?.stats?.category?.breakdown) return dimensionDataCategory;

      return Object.entries(testStats.stats.category.breakdown)
        .map(([key, value]) => ({
          name: key,
          value: value as number,
        }))
        .sort((a, b) => b.value - a.value);
    };

    return generateData();
  }, [testStats]);

  const generateBehaviorDataCallback = useCallback(() => {
    // Define the function inside the callback to avoid recreation on every render
    const generateData = () => {
      if (!testStats?.stats?.behavior?.breakdown) return dimensionDataBehavior;

      return Object.entries(testStats.stats.behavior.breakdown)
        .map(([key, value]) => ({
          name: key,
          value: value as number,
        }))
        .sort((a, b) => b.value - a.value);
    };

    return generateData();
  }, [testStats]);

  const generateTestCasesManagedCallback = useCallback(() => {
    // Define the function inside the callback to avoid recreation on every render
    const generateData = () => {
      if (!testStats) return testCasesManagedData;

      if (testStats.history?.monthly_counts) {
        const monthlyData = chartUtils.createMonthlyData(
          testStats.history.monthly_counts,
          getLastSixMonths()
        );

        // Ensure the most recent month shows the actual current total
        // This handles cases where historical cumulative data doesn't match the current total
        if (monthlyData.length > 0 && testStats.total) {
          const lastMonth = monthlyData[monthlyData.length - 1];
          if (lastMonth.total < testStats.total) {
            lastMonth.total = testStats.total;
          }
        }

        return monthlyData;
      }

      return [{ name: 'Current Total', total: testStats.total || 0 }];
    };

    return generateData();
  }, [testStats]);

  const generateTestExecutionTrendCallback = useCallback(() => {
    // Generate test execution trend data from test results timeline
    const generateData = () => {
      if (
        !testResultsStats?.timeline ||
        testResultsStats.timeline.length === 0
      ) {
        return testTrendData; // Fallback to mock data
      }

      return testResultsStats.timeline
        .sort((a, b) => {
          // Sort by original date format (YYYY-MM) chronologically first
          return a.date.localeCompare(b.date);
        })
        .map(item => ({
          name: formatTimelineDate(item.date),
          tests: item.overall?.total || 0,
          passed: item.overall?.passed || 0,
          failed: item.overall?.failed || 0,
          pass_rate: item.overall?.pass_rate || 0,
        }));
    };

    return generateData();
  }, [testResultsStats]);

  // Memoize chart data to prevent unnecessary recalculations
  const categoryData = useMemo(
    () => generateCategoryDataCallback(),
    [generateCategoryDataCallback]
  );
  const behaviorData = useMemo(
    () => generateBehaviorDataCallback(),
    [generateBehaviorDataCallback]
  );
  const testCasesData = useMemo(
    () => generateTestCasesManagedCallback(),
    [generateTestCasesManagedCallback]
  );
  const testExecutionTrendData = useMemo(
    () => generateTestExecutionTrendCallback(),
    [generateTestExecutionTrendCallback]
  );

  return (
    <>
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {!isLoading && !error && (
        <BaseChartsGrid columns={{ xs: 12, sm: 6, md: 3, lg: 3 }}>
          <BaseLineChart
            title="Cumulative Tests"
            data={testCasesData}
            series={[{ dataKey: 'total', name: 'Total Test Cases' }]}
            useThemeColors={true}
            colorPalette="line"
            height={180}
          />

          <BaseLineChart
            title="Test Execution Trend"
            data={testExecutionTrendData}
            series={[
              {
                dataKey: 'tests',
                name: 'Total Tests',
                color: theme.palette.primary.main,
              }, // Primary blue
              {
                dataKey: 'passed',
                name: 'Passed Tests',
                color: theme.palette.success.main,
              }, // Success green
              {
                dataKey: 'failed',
                name: 'Failed Tests',
                color: theme.palette.error.main,
              }, // Error red
            ]}
            useThemeColors={false}
            colorPalette="line"
            height={180}
          />

          <BasePieChart
            title="Tests Behavior Distribution"
            data={behaviorData}
            useThemeColors={true}
            colorPalette="pie"
          />

          <BasePieChart
            title="Tests Category Distribution"
            data={categoryData}
            useThemeColors={true}
            colorPalette="pie"
          />
        </BaseChartsGrid>
      )}
    </>
  );
}
