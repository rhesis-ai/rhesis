'use client';

import React, { useEffect, useState, useRef } from 'react';
import { BasePieChart, BaseChartsGrid } from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { 
  TestRunStatsStatus, 
  TestRunStatsResults, 
  TestRunStatsTests, 
  TestRunStatsExecutors 
} from '@/utils/api-client/interfaces/test-run-stats';
import { Box, CircularProgress, Typography, Alert, Skeleton } from '@mui/material';

// Fallback mock data in case the API fails
const fallbackData = [
  { name: 'Loading...', value: 100 },
];

// Configuration for each chart
const CHART_CONFIG = {
  status: { top: 5, title: "Test Runs by Status" },
  result: { top: 5, title: "Test Runs by Result" },
  test: { top: 5, title: "Most Run Test Sets" },
  executor: { top: 5, title: "Top Test Executors" }
};

// Helper function to truncate long names for legends
const truncateName = (name: string): string => {
  if (name.length <= 15) return name;
  return `${name.substring(0, 12)}...`;
};

// Using real API interfaces now

interface TestRunChartsProps {
  sessionToken: string;
}

// Individual chart state interfaces
interface ChartState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export default function TestRunCharts({ sessionToken }: TestRunChartsProps) {
  const isMounted = useRef(false);
  
  // Individual state for each chart
  const [statusChart, setStatusChart] = useState<ChartState<TestRunStatsStatus>>({
    data: null,
    loading: false,
    error: null
  });
  
  const [resultChart, setResultChart] = useState<ChartState<TestRunStatsResults>>({
    data: null,
    loading: false,
    error: null
  });
  
  const [testChart, setTestChart] = useState<ChartState<TestRunStatsTests>>({
    data: null,
    loading: false,
    error: null
  });
  
  const [executorChart, setExecutorChart] = useState<ChartState<TestRunStatsExecutors>>({
    data: null,
    loading: false,
    error: null
  });

  useEffect(() => {
    isMounted.current = true;

    // Helper function to create individual chart fetchers
    const createChartFetcher = <T,>(
      mode: 'status' | 'results' | 'test_sets' | 'executors',
      setter: React.Dispatch<React.SetStateAction<ChartState<T>>>,
      chartName: string
    ) => async () => {
      if (!sessionToken) return;
      
      try {
        setter(prev => ({ ...prev, loading: true, error: null }));
        
        const clientFactory = new ApiClientFactory(sessionToken);
        const testRunsClient = clientFactory.getTestRunsClient();
        
        const stats = await testRunsClient.getTestRunStats({
          mode,
          top: 5,  // Limit to top 5 items for charts
          months: 6
        });
        
        if (isMounted.current) {
          setter(prev => ({ 
            ...prev, 
            data: stats as T, 
            loading: false, 
            error: null 
          }));
        }
      } catch (err) {
        console.error(`Error fetching ${chartName} stats:`, err);
        if (isMounted.current) {
          setter(prev => ({ 
            ...prev, 
            loading: false, 
            error: `Failed to load ${chartName} data` 
          }));
        }
      }
    };

    // Create individual fetchers for each chart
    const fetchStatusStats = createChartFetcher('status', setStatusChart, 'status');
    const fetchResultStats = createChartFetcher('results', setResultChart, 'results');
    const fetchTestStats = createChartFetcher('test_sets', setTestChart, 'test sets');
    const fetchExecutorStats = createChartFetcher('executors', setExecutorChart, 'executor');

    // Fetch all charts in parallel for maximum speed
    Promise.all([
      fetchStatusStats(),
      fetchResultStats(),
      fetchTestStats(),
      fetchExecutorStats()
    ]).catch(err => {
      console.error('Error in parallel chart fetching:', err);
    });

    return () => {
      isMounted.current = false;
    };
  }, [sessionToken]);

  // Generate chart data from individual chart states
  const generateStatusData = () => {
    if (!statusChart.data) return fallbackData;
    
    return statusChart.data.status_distribution
      .slice(0, CHART_CONFIG.status.top)
      .map((item) => ({
        name: truncateName(item.status),
        value: item.count,
        fullName: item.status
      }));
  };

  const generateResultData = () => {
    if (!resultChart.data) return fallbackData;
    
    const { result_distribution } = resultChart.data;
    return [
      { name: 'Passed', value: result_distribution.passed, fullName: 'Passed' },
      { name: 'Failed', value: result_distribution.failed, fullName: 'Failed' },
      { name: 'Pending', value: result_distribution.pending, fullName: 'Pending' }
    ].filter(item => item.value > 0);  // Only show categories with data
  };

  const generateTestData = () => {
    if (!testChart.data) return fallbackData;
    
    return testChart.data.most_run_test_sets
      .slice(0, CHART_CONFIG.test.top)
      .map((item) => ({
        name: truncateName(item.test_set_name),
        value: item.run_count,
        fullName: item.test_set_name
      }));
  };

  const generateExecutorData = () => {
    if (!executorChart.data) return fallbackData;
    
    return executorChart.data.top_executors
      .slice(0, CHART_CONFIG.executor.top)
      .map((item) => ({
        name: truncateName(item.executor_name),
        value: item.run_count,
        fullName: item.executor_name
      }));
  };

  // Component for individual chart with loading/error states
  const ChartWithState = ({ 
    chartState, 
    title, 
    dataGenerator 
  }: { 
    chartState: ChartState<any>, 
    title: string, 
    dataGenerator: () => any[] 
  }) => {
    if (chartState.loading) {
      return (
        <Box sx={{ 
          height: 300, 
          display: 'flex', 
          flexDirection: 'column',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          p: 2
        }}>
          <Typography variant="h6" sx={{ mb: 2 }}>{title}</Typography>
          <Box sx={{ 
            flex: 1, 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center' 
          }}>
            <CircularProgress size={40} />
          </Box>
        </Box>
      );
    }

    if (chartState.error) {
      return (
        <Box sx={{ 
          height: 300, 
          display: 'flex', 
          flexDirection: 'column',
          border: '1px solid',
          borderColor: 'error.main',
          borderRadius: 1,
          p: 2,
          bgcolor: 'error.light',
          opacity: 0.1
        }}>
          <Typography variant="h6" sx={{ mb: 2 }}>{title}</Typography>
          <Box sx={{ 
            flex: 1, 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center' 
          }}>
            <Typography color="error" variant="body2" align="center">
              {chartState.error}
            </Typography>
          </Box>
        </Box>
      );
    }

    return (
      <BasePieChart
        title={title}
        data={dataGenerator()}
        useThemeColors={true}
        colorPalette="pie"
      />
    );
  };

  return (
    <BaseChartsGrid>
      <ChartWithState
        chartState={statusChart}
        title={CHART_CONFIG.status.title}
        dataGenerator={generateStatusData}
      />
      
      <ChartWithState
        chartState={resultChart}
        title={CHART_CONFIG.result.title}
        dataGenerator={generateResultData}
      />
      
      <ChartWithState
        chartState={testChart}
        title={CHART_CONFIG.test.title}
        dataGenerator={generateTestData}
      />
      
      <ChartWithState
        chartState={executorChart}
        title={CHART_CONFIG.executor.title}
        dataGenerator={generateExecutorData}
      />
    </BaseChartsGrid>
  );
} 