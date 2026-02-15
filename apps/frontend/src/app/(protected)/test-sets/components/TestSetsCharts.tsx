'use client';

import React, { useEffect, useState, useRef } from 'react';
import {
  BasePieChart,
  BaseLineChart,
  BaseChartsGrid,
} from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestSetStatsResponse } from '@/utils/api-client/interfaces/test-set';
import { useSession } from 'next-auth/react';
import { Box, CircularProgress, Typography, useTheme } from '@mui/material';

// Fallback data for charts when no data is available
const FALLBACK_DATA = {
  noData: [
    { name: 'No Data Available', value: 100, fullName: 'No Data Available' },
  ],
  total: [{ name: 'Current', count: 0 }],
};

// Configuration for each chart
const CHART_CONFIG = {
  status: { top: 5, title: 'Test Sets by Status' },
  creator: { top: 5, title: 'Test Sets by Creator' },
  topics: { top: 5, title: 'Top 5 Topics' },
  total: { title: 'Total Test Sets', months: 6 },
};

// Helper function to truncate long names for legends
const truncateName = (name: string): string => {
  if (name.length <= 15) return name;
  return `${name.substring(0, 12)}...`;
};

// Helper function to calculate the appropriate y-axis domain
const calculateYAxisDomain = (data: { count: number }[]): [number, number] => {
  if (!data.length) return [0, 100];

  // Find the maximum value
  const maxValue = Math.max(...data.map(item => item.count));

  // Round up to the nearest nice value for the upper bound
  // Using a multiplier approach to make the chart look better
  const multiplier =
    maxValue <= 10
      ? 2 // For small values, double it
      : maxValue <= 100
        ? 1.5 // For medium values, add 50%
        : maxValue <= 1000
          ? 1.2 // For larger values, add 20%
          : 1.1; // For very large values, add 10%

  const upperBound = Math.ceil((maxValue * multiplier) / 100) * 100;

  return [0, upperBound];
};

export default function TestSetsCharts() {
  const { data: session } = useSession();
  const theme = useTheme();
  const [testSetStats, setTestSetStats] = useState<TestSetStatsResponse | null>(
    null
  );
  const [topicsStats, setTopicsStats] = useState<TestSetStatsResponse | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const dataFetchedRef = useRef(false);

  useEffect(() => {
    const fetchTestSetStats = async () => {
      // Prevent duplicate fetches when tab regains focus
      if (dataFetchedRef.current) return;

      try {
        setIsLoading(true);
        // Get the session token from the current session
        const sessionToken = session?.session_token || '';
        if (!sessionToken) return;

        const clientFactory = new ApiClientFactory(sessionToken);
        const testSetsClient = clientFactory.getTestSetsClient();

        // Use the maximum top value to fetch data
        const maxTop = Math.max(
          CHART_CONFIG.status.top,
          CHART_CONFIG.creator.top
        );

        // Fetch stats with mode=entity for general test set stats
        const stats = await testSetsClient.getTestSetStats({
          top: maxTop,
          months: CHART_CONFIG.total.months,
          mode: 'entity',
        });
        setTestSetStats(stats);

        // Fetch topics stats with mode=related_entity
        const topicsData = await testSetsClient.getTestSetStats({
          top: CHART_CONFIG.topics.top,
          months: 1,
          mode: 'related_entity',
        });
        setTopicsStats(topicsData);

        setError(null);
        // Mark that we've fetched the data
        dataFetchedRef.current = true;
      } catch (_err) {
        setError('Failed to load test set statistics');
      } finally {
        setIsLoading(false);
      }
    };

    if (session?.session_token) {
      fetchTestSetStats();
    }
  }, [session?.session_token]);

  // Generate line chart data for total test sets, using history data if available
  const generateTotalTestSetsData = () => {
    if (!testSetStats) return FALLBACK_DATA.total;

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
          const formattedMonth = `${monthNames[parseInt(monthNum) - 1]} ${year}`;

          return {
            name: formattedMonth,
            count,
          };
        }
      );
    }

    // Fallback to just current total if no history
    return [{ name: 'Current', count: testSetStats.total }];
  };

  // Generate status data
  const generateStatusData = () => {
    if (!testSetStats?.stats.status) {
      return FALLBACK_DATA.noData;
    }

    const { stats } = testSetStats;
    return Object.entries(stats.status.breakdown)
      .map(([name, value]) => ({
        name: name,
        value: value as number,
        fullName: name,
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, CHART_CONFIG.status.top);
  };

  // Generate creator data using user property
  const generateCreatorData = () => {
    if (!testSetStats?.stats.user) {
      return FALLBACK_DATA.noData;
    }

    const { stats } = testSetStats;
    return Object.entries(stats.user.breakdown)
      .map(([name, value]) => ({
        name: truncateName(name),
        value: value as number,
        fullName: name,
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, CHART_CONFIG.creator.top);
  };

  // Generate topics data with top 5
  const generateTopicsData = () => {
    if (!topicsStats?.stats.topic) {
      return FALLBACK_DATA.noData;
    }

    const { stats } = topicsStats;
    return Object.entries(stats.topic.breakdown)
      .map(([name, value]) => ({
        name: truncateName(name),
        value: value as number,
        fullName: name,
      }))
      .sort((a, b) => b.value - a.value)
      .slice(0, CHART_CONFIG.topics.top);
  };

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
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  // Calculate line chart data
  const lineChartData = generateTotalTestSetsData();
  // Calculate y-axis domain for line chart
  const yAxisDomain = calculateYAxisDomain(lineChartData);

  return (
    <BaseChartsGrid>
      {/* Total Test Sets Line Chart */}
      <BaseLineChart
        title={CHART_CONFIG.total.title}
        data={lineChartData}
        series={[
          {
            dataKey: 'count',
            name: 'Test Sets',
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

      <BasePieChart
        title={CHART_CONFIG.status.title}
        data={generateStatusData()}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
      />

      <BasePieChart
        title={CHART_CONFIG.creator.title}
        data={generateCreatorData()}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
        showPercentage={true}
      />

      <BasePieChart
        title={CHART_CONFIG.topics.title}
        data={generateTopicsData()}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
        showPercentage={true}
      />
    </BaseChartsGrid>
  );
}
