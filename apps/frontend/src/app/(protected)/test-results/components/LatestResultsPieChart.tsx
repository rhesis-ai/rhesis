'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Paper, Typography, CircularProgress, Alert, Box } from '@mui/material';
import { BasePieChart } from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultsStats, PassFailStats } from '@/utils/api-client/interfaces/test-results';
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
    { name: 'Failed', value: failed }
  ].filter(item => item.value > 0);
};

export default function LatestResultsPieChart({ sessionToken, filters }: LatestResultsPieChartProps) {
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
        ...filters
      };

      const statsData = await testResultsClient.getComprehensiveTestResultsStats(options);
      if (statsData && typeof statsData === 'object') {
        setStats(statsData);
        setError(null);
      } else {
        setStats(null);
        setError('Invalid summary data received');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load summary data';
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
      value: isNaN(item.value) ? 0 : item.value
    }));
  }, [stats?.overall_pass_rates]);

  const getContextInfo = () => {
    return 'Distribution of passed and failed tests in the selected period';
  };

  if (isLoading) {
    return (
      <Paper elevation={2} sx={{ p: (theme) => theme.customSpacing.container.medium, height: 400, display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Overall Results
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Distribution of passed and failed tests in the selected period
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
          <CircularProgress size={24} />
          <Typography variant="body2" sx={{ ml: 2, fontSize: '0.875rem' }}>Loading results...</Typography>
        </Box>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper elevation={2} sx={{ p: (theme) => theme.customSpacing.container.medium, height: 400, display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          Overall Results
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Error occurred
        </Typography>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  return (
    <Paper elevation={2} sx={{ p: 3, height: 400, display: 'flex', flexDirection: 'column' }}>
      <Typography variant="h6" sx={{ mb: 1 }}>
        {stats?.metadata?.test_run_id ? 'Test Run Results' : 'Overall Results'}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Distribution of passed and failed tests in the selected period
      </Typography>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <BasePieChart
          title=""
          data={latestRunData}
          useThemeColors={true}
          colorPalette="pie"
          height={240}
          showPercentage={true}
          legendProps={{
            wrapperStyle: { 
              fontSize: '10px',
              marginTop: '15px',
              marginBottom: '10px',
              paddingBottom: '10px'
            }, 
            iconSize: 8,
            layout: 'horizontal',
            verticalAlign: 'bottom',
            align: 'center'
          }}
        />
      </Box>
    </Paper>
  );
}