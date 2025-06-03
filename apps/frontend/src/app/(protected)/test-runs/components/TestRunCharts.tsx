'use client';

import React, { useEffect, useState, useRef } from 'react';
import { BasePieChart, BaseChartsGrid } from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';

// Fallback mock data in case the API fails
const fallbackData = [
  { name: 'Loading...', value: 100 },
];

// Configuration for each chart
const CHART_CONFIG = {
  status: { top: 5, title: "Test Runs by Status" },
  result: { top: 5, title: "Test Runs by Result" },
  test: { top: 5, title: "Most Run Tests" },
  executor: { top: 5, title: "Top Test Executors" }
};

// Helper function to truncate long names for legends
const truncateName = (name: string): string => {
  if (name.length <= 15) return name;
  return `${name.substring(0, 12)}...`;
};

// Temporary interfaces until API client is ready
interface TestRunStats {
  stats: {
    status: {
      breakdown: Record<string, number>;
    };
    result: {
      breakdown: Record<string, number>;
    };
    test: {
      breakdown: Record<string, number>;
    };
    executor: {
      breakdown: Record<string, number>;
    };
  };
}

interface TestRunChartsProps {
  sessionToken: string;
}

export default function TestRunCharts({ sessionToken }: TestRunChartsProps) {
  const isMounted = useRef(false);
  const [testRunStats, setTestRunStats] = useState<TestRunStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    isMounted.current = true;

    const fetchTestRunStats = async () => {
      if (!sessionToken) return;
      
      try {
        setIsLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const testRunsClient = clientFactory.getTestRunsClient();
        
        // Temporarily return mock data until API is ready
        const mockStats: TestRunStats = {
          stats: {
            status: {
              breakdown: {
                'Pending': 5,
                'Running': 3,
                'Completed': 10,
                'Failed': 2
              }
            },
            result: {
              breakdown: {
                'Pass': 8,
                'Fail': 2,
                'Error': 1,
                'Skipped': 1
              }
            },
            test: {
              breakdown: {
                'Test 1': 5,
                'Test 2': 4,
                'Test 3': 3,
                'Test 4': 2,
                'Test 5': 1
              }
            },
            executor: {
              breakdown: {
                'User 1': 6,
                'User 2': 4,
                'User 3': 3,
                'User 4': 2
              }
            }
          }
        };
        
        if (isMounted.current) {
          setTestRunStats(mockStats);
          setError(null);
        }
      } catch (err) {
        console.error('Error fetching test run stats:', err);
        if (isMounted.current) {
          setError('Failed to load test run statistics');
        }
      } finally {
        if (isMounted.current) {
          setIsLoading(false);
        }
      }
    };

    fetchTestRunStats();

    return () => {
      isMounted.current = false;
    };
  }, [sessionToken]);

  // Generate chart data from test run stats with individual limits
  const generateStatusData = () => {
    if (!testRunStats) return fallbackData;
    
    const { stats } = testRunStats;
    return Object.entries(stats.status.breakdown)
      .slice(0, CHART_CONFIG.status.top)
      .map(([name, value]) => ({
        name: truncateName(name),
        value: value as number,
        fullName: name
      }));
  };

  const generateResultData = () => {
    if (!testRunStats) return fallbackData;
    
    const { stats } = testRunStats;
    return Object.entries(stats.result.breakdown)
      .slice(0, CHART_CONFIG.result.top)
      .map(([name, value]) => ({
        name: truncateName(name),
        value: value as number,
        fullName: name
      }));
  };

  const generateTestData = () => {
    if (!testRunStats) return fallbackData;
    
    const { stats } = testRunStats;
    return Object.entries(stats.test.breakdown)
      .slice(0, CHART_CONFIG.test.top)
      .map(([name, value]) => ({
        name: truncateName(name),
        value: value as number,
        fullName: name
      }));
  };

  const generateExecutorData = () => {
    if (!testRunStats) return fallbackData;
    
    const { stats } = testRunStats;
    return Object.entries(stats.executor.breakdown)
      .slice(0, CHART_CONFIG.executor.top)
      .map(([name, value]) => ({
        name: truncateName(name),
        value: value as number,
        fullName: name
      }));
  };

  if (isLoading && !testRunStats) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

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