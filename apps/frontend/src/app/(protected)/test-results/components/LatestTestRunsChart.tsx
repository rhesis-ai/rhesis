'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Paper, Typography, CircularProgress, Alert, Box, useTheme } from '@mui/material';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultsStats, TestRunSummaryItem } from '@/utils/api-client/interfaces/test-results';
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
    { name: 'Test Run 5', pass_rate: 95, total: 75, passed: 71, failed: 4 }
  ];

  // Return mock data if no valid test run summary
  if (!Array.isArray(testRunSummary) || testRunSummary.length === 0) {
    return mockData;
  }
  
  // Create a copy of the array to avoid mutating the original
  const runs = [...testRunSummary];
  
  // Sort by started_at (most recent first) and take last 10
  const sortedRuns = runs
    .sort((a, b) => {
      const dateA = a.started_at ? new Date(a.started_at).getTime() : 0;
      const dateB = b.started_at ? new Date(b.started_at).getTime() : 0;
      return dateB - dateA; // Most recent first
    })
    .slice(0, 5) // Take the 5 most recent
    .reverse(); // Reverse to show chronologically (oldest to newest for chart)

  return sortedRuns.map((item) => {
    // Use the name field from the test run data
    const runName = item.name || 'Unnamed Run';

    return {
      name: runName,
      pass_rate: item.overall?.pass_rate != null ? Math.round(item.overall.pass_rate * 10) / 10 : 0,
      total: item.overall?.total || 0,
      passed: item.overall?.passed || 0,
      failed: item.overall?.failed || 0,
      test_run_id: item.id
    };
  });
};

export default function LatestTestRunsChart({ sessionToken, filters }: LatestTestRunsChartProps) {
  const theme = useTheme();
  
  // Use a consistent blue color for pass rates that works in both light and dark themes
  // This matches the first color in the default pie chart palette
  const passRateColor = '#8884d8'; // Blue color that works in both light and dark themes
  
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
        ...filters
      };

      const statsData = await testResultsClient.getComprehensiveTestResultsStats(options);
      if (statsData && typeof statsData === 'object') {
        console.log('Test Runs API Response:', statsData);
        console.log('Test runs data:', statsData.test_run_summary);
        setStats(statsData);
        setError(null);
      } else {
        setStats(null);
        setError('Invalid test runs data received');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load test runs data';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [sessionToken, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const testRunsData = useMemo(() => {
    console.log('Raw test runs data:', stats?.test_run_summary);
    const data = transformTestRunsData(stats?.test_run_summary);
    console.log('Transformed test runs data:', data);
    const finalData = data.map(item => ({
      ...item,
      pass_rate: isNaN(item.pass_rate) ? 0 : item.pass_rate
    }));
    console.log('Final test runs data for chart:', finalData);
    return finalData;
  }, [stats?.test_run_summary]);

  const getContextInfo = () => {
    return 'Pass rates from the 5 most recent test executions';
  };

  if (isLoading) {
    return (
      <Paper elevation={1} sx={{ p: 3, height: 400, display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Latest Test Runs
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Pass rates from the 5 most recent test executions
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
          <CircularProgress size={24} />
          <Typography variant="body2" sx={{ ml: 2, fontSize: '0.875rem' }}>Loading test runs...</Typography>
        </Box>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper elevation={1} sx={{ p: 3, height: 400, display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Latest Test Runs
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Error occurred
        </Typography>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  return (
    <Paper elevation={1} sx={{ p: 3, height: 400, display: 'flex', flexDirection: 'column' }}>
      <Typography variant="h6" sx={{ mb: 1 }}>
        Latest Test Runs
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Pass rates from the 5 most recent test executions
      </Typography>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart
            margin={{ top: 30, right: 15, bottom: 5, left: -15 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="name"
              type="category"
              name="Test Run"
              angle={-45}
              textAnchor="end"
              interval={0}
              tick={{ fontSize: 10 }}
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
              tick={{ fontSize: 10 }}
              axisLine={{ strokeWidth: 1 }}
              tickLine={{ strokeWidth: 1 }}
              tickFormatter={(value: number) => `${value}%`}
            />
            <Tooltip 
              contentStyle={{ fontSize: '10px' }}
              formatter={(value: any, name: string) => {
                if (name === 'Pass Rate') return [`${value}%`, name];
                return [value, name];
              }}
            />
            <Legend 
              payload={[
                {
                  value: 'Pass Rate',
                  type: 'circle',
                  color: passRateColor // Use consistent blue color for pass rates
                }
              ]}
              wrapperStyle={{ fontSize: '10px' }}
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
