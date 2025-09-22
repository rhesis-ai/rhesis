'use client';

import React from 'react';
import { BasePieChart, BaseLineChart, BaseChartsGrid } from '@/components/common/BaseCharts';
import { Box, CircularProgress, Typography, Alert, useTheme } from '@mui/material';

// Fallback mock data in case the API fails
const fallbackData = [
  { name: 'No Data Available', value: 100, fullName: 'No Data Available' },
];

// Fallback data for line chart
const fallbackLineData = [
  { name: 'Current', count: 0 },
];

interface TestDetailChartsProps {
  testId: string;
  sessionToken: string;
}

export default function TestDetailCharts({ testId, sessionToken }: TestDetailChartsProps) {
  const theme = useTheme();
  // This is a placeholder component with empty charts
  // The actual implementation will be added later
  
  return (
    <BaseChartsGrid>
      {/* Total Executions Line Chart */}
      <BaseLineChart
        title="Total Executions"
        data={fallbackLineData}
        series={[
          {
            dataKey: 'count',
            name: 'Executions',
            strokeWidth: 2
          }
        ]}
        useThemeColors={true}
        colorPalette="line"
        height={180}
        legendProps={{ wrapperStyle: { fontSize: theme.typography.chartTick.fontSize }, iconSize: 8, layout: 'horizontal' }}
        yAxisConfig={{
          domain: [0, 100],
          allowDataOverflow: true
        }}
      />
      
      {/* Success Rate Chart */}
      <BasePieChart
        title="Success Rate"
        data={fallbackData}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
        showPercentage={true}
      />
      
      {/* Execution Time Chart */}
      <BasePieChart
        title="Average Execution Time"
        data={fallbackData}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
        showPercentage={true}
      />
      
      {/* Failure Reasons Chart */}
      <BasePieChart
        title="Failure Reasons"
        data={fallbackData}
        useThemeColors={true}
        colorPalette="pie"
        height={180}
        showPercentage={true}
      />
    </BaseChartsGrid>
  );
} 