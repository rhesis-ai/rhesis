'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import {
  BasePieChart,
  BaseLineChart,
  BaseChartsGrid,
} from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSetDetailStatsResponse } from '@/utils/api-client/interfaces/test-set';
import { Box, CircularProgress, Alert, useTheme } from '@mui/material';
import { pieChartUtils } from '@/components/common/BasePieChart';

// Fallback mock data in case the API fails
const fallbackData = [{ name: 'Loading...', value: 100 }];

// Fallback data for total test sets line chart
const fallbackTotalData = [{ name: 'Current', count: 0 }];

// Dynamic configuration for charts - will be determined based on API response
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
    maxValue <= 10 ? 2 : maxValue <= 100 ? 1.5 : maxValue <= 1000 ? 1.2 : 1.1;

  const upperBound = Math.ceil((maxValue * multiplier) / 10) * 10;

  return [0, upperBound];
};

// Helper function to generate a title for a dimension
const generateDimensionTitle = (dimension: string): string => {
  return pieChartUtils.generateDimensionTitle(dimension);
};

interface TestSetDetailChartsProps {
  testSetId: string;
  sessionToken: string;
}

export default function TestSetDetailCharts({
  testSetId,
  sessionToken,
}: TestSetDetailChartsProps) {
  const theme = useTheme();
  const [testSetStats, setTestSetStats] =
    useState<TestSetDetailStatsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Define allowedDimensions inside useMemo
  const memoizedAllowedDimensions = useMemo(() => {
    // Define the array inside to avoid recreation on every render
    return ['behavior', 'category', 'topic'];
  }, []);

  // Generate line chart data for total tests, using history data if available
  const generateTotalTestsLineData = useCallback((): LineChartDataItem[] => {
    if (!testSetStats) return fallbackTotalData;

    if (testSetStats.history && testSetStats.history.monthly_counts) {
      // Use history data for the line chart
      return Object.entries(testSetStats.history.monthly_counts).map(
        ([month, count]) => {
          // Format month for better display: YYYY-MM to MMM YYYY (e.g., "2025-01" to "Jan 2025")
          const [year, monthNum] = month.split('-');
          const monthNames = [
            'Jan',
            'Feb',
            'Mar',
            'Apr',
            'May',
            'Jun',
            'Jul',
            'Aug',
            'Sep',
            'Oct',
            'Nov',
            'Dec',
          ];
          const formattedMonth =
            monthNum && parseInt(monthNum) >= 1 && parseInt(monthNum) <= 12
              ? `${monthNames[parseInt(monthNum) - 1]} ${year}`
              : month;

          return {
            name: formattedMonth,
            count: typeof count === 'number' ? count : 0,
          };
        }
      );
    }

    // Fallback to just current total if no history
    return [
      {
        name: 'Current',
        count: typeof testSetStats.total === 'number' ? testSetStats.total : 0,
      },
    ];
  }, [testSetStats]);

  // Generic function to generate chart data for any dimension
  const generateDimensionData = useCallback(
    (dimension: string): ChartDataItem[] => {
      if (
        !testSetStats?.stats?.[dimension]?.breakdown ||
        !testSetStats?.stats?.[dimension]?.total
      ) {
        return fallbackData;
      }

      return pieChartUtils.generateDimensionData(
        testSetStats.stats[dimension].breakdown,
        testSetStats.stats[dimension].total,
        DEFAULT_TOP,
        fallbackData
      );
    },
    [testSetStats]
  );

  useEffect(() => {
    const fetchTestSetStats = async () => {
      if (!testSetId) return;

      try {
        setIsLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const testSetsClient = clientFactory.getTestSetsClient();

        const stats = await testSetsClient.getTestSetDetailStats(testSetId, {
          top: DEFAULT_TOP,
          months: DEFAULT_MONTHS,
          mode: 'related_entity',
        });
        setTestSetStats(stats);

        setError(null);
      } catch (err) {
        const errorMessage =
          err instanceof Error
            ? err.message
            : 'Failed to load test statistics for this test set';
        setError(errorMessage);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTestSetStats();
  }, [testSetId, sessionToken]);

  // Calculate line chart data
  const lineChartData = useMemo(
    () => generateTotalTestsLineData(),
    [generateTotalTestsLineData]
  );

  // Calculate y-axis domain for line chart
  const yAxisDomain = useMemo(
    () => calculateDomain(lineChartData),
    [lineChartData]
  );

  // Memoize dimension data for pie charts
  const dimensionChartData = useMemo(() => {
    return memoizedAllowedDimensions.map(dimension => ({
      dimension,
      title: generateDimensionTitle(dimension),
      data: generateDimensionData(dimension),
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
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <BaseChartsGrid>
      {/* Total Tests Line Chart */}
      <BaseLineChart
        title="Total Tests "
        data={lineChartData}
        series={[
          {
            dataKey: 'count',
            name: 'Tests Count',
            strokeWidth: 2,
          },
        ]}
        useThemeColors={true}
        colorPalette="line"
        height={180}
        legendProps={{
          wrapperStyle: { fontSize: theme.typography.chartTick.fontSize },
          iconSize: 8,
          layout: 'horizontal',
        }}
        yAxisConfig={{
          domain: yAxisDomain,
          allowDataOverflow: true,
        }}
      />

      {/* Show the pie charts for behavior, category, topic (in that order) */}
      {dimensionChartData.map(({ dimension, title, data }) => (
        <BasePieChart
          key={dimension}
          title={title}
          data={data}
          useThemeColors={true}
          colorPalette="pie"
          height={180}
          showPercentage={true}
          tooltipProps={{
            contentStyle: {
              fontSize: theme.typography.chartTick.fontSize,
              backgroundColor: theme.palette.background.paper,
              border: `1px solid ${theme.palette.divider}`,
              borderRadius: '4px',
              color: theme.palette.text.primary,
            },
            itemStyle: {
              color: theme.palette.text.primary,
            },
            labelStyle: {
              color: theme.palette.text.primary,
            },
            formatter: (
              value: number,
              name: string,
              props: { payload: { percentage: string; fullName?: string } }
            ) => {
              const item = props.payload;
              return [`${value} (${item.percentage})`, item.fullName || name];
            },
          }}
        />
      ))}
    </BaseChartsGrid>
  );
}
