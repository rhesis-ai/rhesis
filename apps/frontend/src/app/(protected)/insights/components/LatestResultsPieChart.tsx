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
import { BasePieChart } from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  TestResultsStats,
  PassFailStats,
} from '@/utils/api-client/interfaces/test-results';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';

interface LatestResultsPieChartProps {
  sessionToken: string;
  filters: Partial<TestResultsStatsOptions>;
}

const transformPassFailToChartData = (stats?: PassFailStats) => {
  if (!stats) return [{ name: 'No Data', value: 1 }];

  const passed = stats.passed || 0;
  const failed = stats.failed || 0;

  if (passed === 0 && failed === 0) {
    return [{ name: 'No Data', value: 1 }];
  }

  return [
    { name: 'Passed', value: passed },
    { name: 'Failed', value: failed },
  ].filter(item => item.value > 0);
};

export default function LatestResultsPieChart({
  sessionToken,
  filters,
}: LatestResultsPieChartProps) {
  const theme = useTheme();
  const [stats, setStats] = useState<TestResultsStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();

      const options: TestResultsStatsOptions = {
        mode: 'summary', // Specific mode for overall stats
        months: filters.months || 6,
        ...filters,
      };

      const statsData =
        await testResultsClient.getComprehensiveTestResultsStats(options);
      if (statsData && typeof statsData === 'object') {
        setStats(statsData);
        setError(null);
      } else {
        setStats(null);
        setError('Invalid summary data received');
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load summary data';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [sessionToken, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const latestRunData = useMemo(() => {
    const data = transformPassFailToChartData(stats?.overall_pass_rates);
    return data.map(item => ({
      ...item,
      value: isNaN(item.value) ? 0 : item.value,
    }));
  }, [stats?.overall_pass_rates]);

  const _getContextInfo = () => {
    return 'Distribution of passed and failed tests in the selected period';
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
          Overall Results
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mb: theme.customSpacing.section.small }}
        >
          Distribution of passed and failed tests in the selected period
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
            Loading results...
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
          Overall Results
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
        {stats?.metadata?.test_run_id ? 'Test Run Results' : 'Overall Results'}
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
        Distribution of passed and failed tests in the selected period
      </Typography>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <BasePieChart
          title=""
          data={latestRunData}
          useThemeColors={true}
          colorPalette="pie"
          height={300}
          innerRadius={40}
          outerRadius={90}
          showPercentage={true}
          elevation={0}
          preventLegendOverflow={true}
          variant="test-results"
          legendProps={{
            wrapperStyle: {
              fontSize: theme.typography.chartTick.fontSize,
              marginTop: theme.spacing(1.875),
              marginBottom: theme.spacing(1.25),
              paddingBottom: theme.spacing(1.25),
            },
            iconSize: 8,
            layout: 'horizontal',
            verticalAlign: 'bottom',
            align: 'center',
          }}
        />
      </Box>
    </Paper>
  );
}
