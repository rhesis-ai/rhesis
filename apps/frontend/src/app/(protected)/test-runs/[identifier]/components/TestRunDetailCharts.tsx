'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { BasePieChart, BaseLineChart, BaseChartsGrid } from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';
import { useChartColors } from '@/components/common/BaseCharts';
import { pieChartUtils } from '@/components/common/BasePieChart';

// Fallback mock data in case the API fails
const fallbackData = [
  { name: 'Loading...', value: 100 },
];

// Define interfaces for the stats data
interface StatsBreakdown {
  dimension: string;
  total: number;
  breakdown: Record<string, number>;
}

interface TestRunStats {
  total: number;
  stats: {
    status: StatsBreakdown;
    result: StatsBreakdown;
    executor: StatsBreakdown;
  };
  history?: {
    monthly_counts: Record<string, number>;
  };
}

// Mock data for test run stats
const mockTestRunStats: TestRunStats = {
  total: 150,
  stats: {
    status: {
      dimension: 'status',
      total: 150,
      breakdown: {
        'Running': 45,
        'Completed': 65,
        'Failed': 25,
        'Pending': 15
      }
    },
    result: {
      dimension: 'result',
      total: 150,
      breakdown: {
        'Pass': 85,
        'Fail': 35,
        'Error': 20,
        'Skipped': 10
      }
    },
    executor: {
      dimension: 'executor',
      total: 150,
      breakdown: {
        'User 1': 50,
        'User 2': 40,
        'User 3': 35,
        'User 4': 25
      }
    }
  },
  history: {
    monthly_counts: {
      '2024-01': 25,
      '2024-02': 35,
      '2024-03': 45,
      '2024-04': 55,
      '2024-05': 65,
      '2024-06': 75
    }
  }
};

// Dynamic configuration for charts
const DEFAULT_TOP = 5;
const DEFAULT_MONTHS = 6;

// Interface for chart data items with better type safety
interface ChartDataItem {
  name: string;
  value: number;
  fullName?: string;
  percentage?: string;
}

interface LineChartDataItem {
  name: string;
  count: number;
}

// Helper function to calculate y-axis domain for line charts
const calculateDomain = (data: LineChartDataItem[]): [number, number] => {
  if (!data.length) return [0, 100];
  
  // Find the maximum value
  const maxValue = Math.max(...data.map(item => item.count));
  
  // Round up to the nearest nice value for the upper bound
  const multiplier = 
    maxValue <= 10 ? 2 :
    maxValue <= 100 ? 1.5 :
    maxValue <= 1000 ? 1.2 :
    1.1;
  
  const upperBound = Math.ceil(maxValue * multiplier / 10) * 10;
  
  return [0, upperBound];
};

interface TestRunDetailChartsProps {
  testRunId: string;
  sessionToken: string;
}

export default function TestRunDetailCharts({ testRunId, sessionToken }: TestRunDetailChartsProps) {
  const [testRunStats, setTestRunStats] = useState<TestRunStats>(mockTestRunStats);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Define allowedDimensions inside useMemo
  const memoizedAllowedDimensions = useMemo(() => {
    return ['status', 'result', 'executor'] as const;
  }, []);

  // Generate line chart data for total tests, using history data if available
  const generateTotalTestsLineData = useCallback((): LineChartDataItem[] => {
    if (!testRunStats) return [{ name: 'Current', count: 0 }];
    
    if (testRunStats.history && testRunStats.history.monthly_counts) {
      // Use history data for the line chart
      return Object.entries(testRunStats.history.monthly_counts).map(([month, count]) => {
        // Format month for better display: YYYY-MM to MMM YYYY (e.g., "2025-01" to "Jan 2025")
        const [year, monthNum] = month.split('-');
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const formattedMonth = monthNum && parseInt(monthNum) >= 1 && parseInt(monthNum) <= 12 
          ? `${monthNames[parseInt(monthNum) - 1]} ${year}` 
          : month;
        
        return {
          name: formattedMonth,
          count: typeof count === 'number' ? count : 0
        };
      });
    }
    
    // Fallback to just current total if no history
    return [{ 
      name: 'Current', 
      count: typeof testRunStats.total === 'number' ? testRunStats.total : 0 
    }];
  }, [testRunStats]);

  // Generic function to generate chart data for any dimension
  const generateDimensionData = useCallback((dimension: keyof TestRunStats['stats']): ChartDataItem[] => {
    if (!testRunStats?.stats?.[dimension]?.breakdown || !testRunStats?.stats?.[dimension]?.total) {
      return fallbackData;
    }
    
    return pieChartUtils.generateDimensionData(
      testRunStats.stats[dimension].breakdown,
      testRunStats.stats[dimension].total,
      5, // Default top 5
      fallbackData
    );
  }, [testRunStats]);

  // Calculate line chart data
  const lineChartData = useMemo(() => generateTotalTestsLineData(), [generateTotalTestsLineData]);
  
  // Calculate y-axis domain for line chart
  const yAxisDomain = useMemo(() => calculateDomain(lineChartData), [lineChartData]);

  // Memoize dimension data for pie charts
  const dimensionChartData = useMemo(() => {
    return memoizedAllowedDimensions.map(dimension => ({
      dimension,
      title: pieChartUtils.generateDimensionTitle(dimension),
      data: generateDimensionData(dimension)
    }));
  }, [memoizedAllowedDimensions, generateDimensionData]);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error">
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <BaseChartsGrid>
      {/* Total Tests Line Chart */}
      <BaseLineChart
        title="Total Tests"
        data={lineChartData}
        series={[
          {
            dataKey: 'count',
            name: 'Tests Count',
            strokeWidth: 2
          }
        ]}
        useThemeColors={true}
        colorPalette="line"
        height={180}
        legendProps={{ wrapperStyle: { fontSize: '10px' }, iconSize: 8, layout: 'horizontal' }}
        yAxisConfig={{
          domain: yAxisDomain,
          allowDataOverflow: true
        }}
      />
      
      {/* Show the pie charts for status, result, executor */}
      {dimensionChartData.map(({ dimension, title, data }) => (
        <BasePieChart
          key={dimension}
          title={title}
          data={data}
          useThemeColors={true}
          colorPalette={dimension === 'status' ? 'status' : 'pie'}
          height={180}
          showPercentage={true}
          tooltipProps={{ 
            contentStyle: { fontSize: '10px' },
            formatter: (value: number, name: string, props: any) => {
              const item = props.payload;
              return [`${value} (${item.percentage})`, item.fullName || name];
            }
          }}
        />
      ))}
    </BaseChartsGrid>
  );
} 