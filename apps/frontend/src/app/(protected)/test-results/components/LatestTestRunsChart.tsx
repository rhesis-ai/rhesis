'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Paper,
  Typography,
  CircularProgress,
  Alert,
  Box,
  useTheme,
} from '@mui/material';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TestResultsStats,
  TestRunSummaryItem,
} from '@/utils/api-client/interfaces/test-results';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';

interface LatestTestRunsChartProps {
  sessionToken: string;
  filters: Partial<TestResultsStatsOptions>;
}

const transformTestRunsData = (testRunSummary?: Array<TestRunSummaryItem>) => {
  // Generate mock data for demonstration
  const mockData = [
    { name: 'Test Run 1', pass_rate: 85, total: 120, passed: 102, failed: 18 },
    { name: 'Test Run 2', pass_rate: 78, total: 95, passed: 74, failed: 21 },
    { name: 'Test Run 3', pass_rate: 92, total: 88, passed: 81, failed: 7 },
    { name: 'Test Run 4', pass_rate: 88, total: 110, passed: 97, failed: 13 },
    { name: 'Test Run 5', pass_rate: 95, total: 75, passed: 71, failed: 4 },
  ];

  // Return mock data if no valid test run summary
  if (!Array.isArray(testRunSummary) || testRunSummary.length === 0) {
    return mockData;
  }

  // Create a copy of the array to avoid mutating the original
  const runs = [...testRunSummary];

  // Sort by started_at (most recent first)
  const sortedRuns = runs
    .sort((a, b) => {
      const dateA = a.started_at ? new Date(a.started_at).getTime() : 0;
      const dateB = b.started_at ? new Date(b.started_at).getTime() : 0;
      return dateB - dateA; // Most recent first
    })
    .reverse(); // Reverse to show chronologically (oldest to newest for chart)

  return sortedRuns.map(item => {
    // Use the name field from the test run data
    const runName = item.name || 'Unnamed Run';

    return {
      name: runName,
      pass_rate:
        item.overall?.pass_rate != null
          ? Math.round(item.overall.pass_rate * 10) / 10
          : 0,
      total: item.overall?.total || 0,
      passed: item.overall?.passed || 0,
      failed: item.overall?.failed || 0,
      test_run_id: item.id,
    };
  });
};

export default function LatestTestRunsChart({
  sessionToken,
  filters,
}: LatestTestRunsChartProps) {
  const theme = useTheme();

  // Convert rem to pixels for Recharts (assuming 1rem = 16px)
  const getPixelFontSize = (remSize: string): number => {
    const remValue = parseFloat(remSize);
    return remValue * 16;
  };

  // Use a consistent blue color for pass rates that works in both light and dark themes
  // This matches the first color in the theme's line chart palette
  const passRateColor = theme.chartPalettes.line[0]; // Primary blue from theme

  const [stats, setStats] = useState<TestResultsStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();

      const options: TestResultsStatsOptions = {
        mode: 'test_runs', // Specific mode for test runs data
        ...filters,
      };

      const statsData =
        await testResultsClient.getComprehensiveTestResultsStats(options);
      if (statsData && typeof statsData === 'object') {
        setStats(statsData);
        setError(null);
      } else {
        setStats(null);
        setError('Invalid test runs data received');
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load test runs data';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [sessionToken, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const testRunsData = useMemo(() => {
    const data = transformTestRunsData(stats?.test_run_summary);
    const finalData = data.map(item => ({
      ...item,
      pass_rate: isNaN(item.pass_rate) ? 0 : item.pass_rate,
    }));
    return finalData;
  }, [stats?.test_run_summary]);

  const getContextInfo = () => {
    const count = stats?.test_run_summary?.length || 0;
    return count > 0
      ? `Pass rates from ${count} test execution${count !== 1 ? 's' : ''} based on current filters`
      : 'Pass rates from filtered test executions';
  };

  if (isLoading) {
    return (
      <Paper
        elevation={theme.elevation.standard}
        sx={{
          p: theme.customSpacing.container.medium,
          height: 400,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Typography variant="h6" sx={{ mb: theme.customSpacing.section.small }}>
          Latest Test Runs
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mb: theme.customSpacing.section.small }}
        >
          Pass rates from filtered test executions
        </Typography>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            flex: 1,
          }}
        >
          <CircularProgress size={24} />
          <Typography
            variant="helperText"
            sx={{ ml: theme.customSpacing.container.small }}
          >
            Loading test runs...
          </Typography>
        </Box>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper
        elevation={theme.elevation.standard}
        sx={{
          p: theme.customSpacing.container.medium,
          height: 400,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Typography variant="h6" sx={{ mb: theme.customSpacing.section.small }}>
          Latest Test Runs
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mb: theme.customSpacing.section.small }}
        >
          Error occurred
        </Typography>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  return (
    <Paper
      elevation={theme.elevation.standard}
      sx={{
        p: theme.customSpacing.container.medium,
        height: 400,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Typography variant="h6" sx={{ mb: theme.customSpacing.section.small }}>
        Latest Test Runs
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{
          mb: theme.customSpacing.section.small,
          minHeight: '2.5rem', // Ensure consistent height for 2 lines
          display: 'flex',
          alignItems: 'flex-start',
        }}
      >
        {getContextInfo()}
      </Typography>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart margin={{ top: 5, right: 15, bottom: 35, left: -15 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="name"
              type="category"
              name="Test Run"
              angle={-45}
              textAnchor="end"
              interval={0}
              tick={{
                fontSize: getPixelFontSize(
                  String(theme.typography.chartTick.fontSize)
                ),
                fill: theme.palette.text.primary,
              }}
              height={60}
              axisLine={{ strokeWidth: 1 }}
              tickLine={{ strokeWidth: 1 }}
            />
            <YAxis
              type="number"
              dataKey="pass_rate"
              name="Pass Rate"
              domain={[0, 100]}
              tickCount={6}
              tick={{
                fontSize: getPixelFontSize(
                  String(theme.typography.chartTick.fontSize)
                ),
                fill: theme.palette.text.primary,
              }}
              axisLine={{ strokeWidth: 1 }}
              tickLine={{ strokeWidth: 1 }}
              tickFormatter={(value: number) => `${value}%`}
            />
            <Tooltip
              contentStyle={{
                fontSize: String(theme.typography.chartTick.fontSize),
                backgroundColor: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: '4px',
                color: theme.palette.text.primary,
              }}
              itemStyle={{
                color: theme.palette.text.primary,
              }}
              labelStyle={{
                color: theme.palette.text.primary,
              }}
              formatter={(value: string | number) => {
                // The value here is the pass_rate from the data
                return [`${value}%`, 'Pass Rate'];
              }}
              labelFormatter={(label: string) => {
                // The label is the test run name
                return label || 'Test Run';
              }}
            />
            <Legend
              payload={[
                {
                  value: 'Pass Rate',
                  type: 'circle',
                  color: passRateColor, // Use consistent blue color for pass rates
                },
              ]}
              wrapperStyle={{
                fontSize: String(theme.typography.chartTick.fontSize),
              }}
              iconSize={8}
              height={30}
            />
            <Scatter
              name="Pass Rate"
              data={testRunsData}
              fill={passRateColor} // Use consistent blue color for pass rates
              line={false}
              shape="circle"
              legendType="circle"
            />
          </ScatterChart>
        </ResponsiveContainer>
      </Box>
    </Paper>
  );
}
