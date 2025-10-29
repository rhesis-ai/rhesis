'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useSession } from 'next-auth/react';
import {
  Box,
  CircularProgress,
  Alert,
  Grid,
  Paper,
  Typography,
  useTheme,
} from '@mui/material';
import { PieChart } from '@mui/x-charts/PieChart';
import { useRouter } from 'next/navigation';
import {
  TestRunStatsStatus,
  TestRunStatsResults,
} from '@/utils/api-client/interfaces/test-run-stats';

export default function DashboardCharts() {
  const { data: session } = useSession();
  const router = useRouter();
  const theme = useTheme();
  const [statusChart, setStatusChart] = useState<TestRunStatsStatus | null>(
    null
  );
  const [resultChart, setResultChart] = useState<TestRunStatsResults | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Use memoized session token to prevent unnecessary re-renders from session object recreation
  const sessionToken = React.useMemo(
    () => session?.session_token,
    [session?.session_token]
  );

  // Get brand colors from theme - matching BasePieChart color palette
  const brandColors = useMemo(
    () => [
      theme.palette.primary.main,
      theme.palette.secondary.main,
      theme.palette.warning.main,
      theme.palette.info.main,
      `${theme.palette.primary.main}99`, // 60% opacity
      `${theme.palette.secondary.main}99`, // 60% opacity
    ],
    [theme]
  );

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setIsLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken || '');
        const testRunsClient = clientFactory.getTestRunsClient();

        // Use the same API calls as TestRunCharts
        const [statusStats, resultStats] = await Promise.all([
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
        ]);

        setStatusChart(statusStats as TestRunStatsStatus);
        setResultChart(resultStats as TestRunStatsResults);
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

  // Prepare data for pie charts - matching TestRunCharts data format
  const statusData = useMemo(() => {
    if (!statusChart?.status_distribution) return [];
    return statusChart.status_distribution.slice(0, 5).map(item => ({
      label: item.status,
      value: item.count,
      id: item.status,
    }));
  }, [statusChart]);

  const resultData = useMemo(() => {
    if (!resultChart?.result_distribution) return [];
    const { result_distribution } = resultChart;
    return [
      { label: 'Passed', value: result_distribution.passed, id: 'passed' },
      { label: 'Failed', value: result_distribution.failed, id: 'failed' },
      { label: 'Pending', value: result_distribution.pending, id: 'pending' },
    ].filter(item => item.value > 0);
  }, [resultChart]);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <>
      {/* Test Runs by Status - Pie Chart */}
      <Grid item xs={12} md={6}>
        <Paper
          sx={{ p: 3, height: '400px', maxHeight: '400px', overflow: 'hidden' }}
        >
          <Typography variant="h6" sx={{ mb: 2 }}>
            Test Runs by Status
          </Typography>
          {statusData.length > 0 ? (
            <PieChart
              series={[
                {
                  data: statusData,
                  highlightScope: { fade: 'global', highlight: 'item' },
                  innerRadius: 50,
                  outerRadius: 120,
                  paddingAngle: 2,
                  cornerRadius: 5,
                  id: 'status-distribution',
                },
              ]}
              height={320}
              margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
              colors={brandColors}
              sx={{
                cursor: 'pointer',
                '& .MuiChartsLegend-root': {
                  display: 'none !important',
                },
              }}
            />
          ) : (
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: 320,
              }}
            >
              <Typography color="text.secondary">
                No test run data available
              </Typography>
            </Box>
          )}
        </Paper>
      </Grid>

      {/* Test Runs by Result - Pie Chart */}
      <Grid item xs={12} md={6}>
        <Paper
          sx={{ p: 3, height: '400px', maxHeight: '400px', overflow: 'hidden' }}
        >
          <Typography variant="h6" sx={{ mb: 2 }}>
            Tests by Result
          </Typography>
          {resultData.length > 0 ? (
            <PieChart
              series={[
                {
                  data: resultData,
                  highlightScope: { fade: 'global', highlight: 'item' },
                  innerRadius: 50,
                  outerRadius: 120,
                  paddingAngle: 2,
                  cornerRadius: 5,
                  id: 'result-distribution',
                },
              ]}
              height={320}
              margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
              colors={brandColors}
              sx={{
                cursor: 'pointer',
                '& .MuiChartsLegend-root': {
                  display: 'none !important',
                },
              }}
            />
          ) : (
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: 320,
              }}
            >
              <Typography color="text.secondary">
                No test run data available
              </Typography>
            </Box>
          )}
        </Paper>
      </Grid>
    </>
  );
}
