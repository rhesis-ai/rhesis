/* eslint-disable react/no-array-index-key -- Chart series rendering */

import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Typography, Box, Card, CardContent, useTheme } from '@mui/material';
import { format, subMonths } from 'date-fns';
import styles from '@/styles/BaseLineChart.module.css';

export interface LineDataSeries {
  dataKey: string;
  color?: string;
  strokeWidth?: number;
  name?: string;
}

// Define interface for month data point
export interface MonthDataPoint {
  name: string;
  date: Date;
  tests: number;
  passed: number;
  total: number;
  monthKey: string;
  [key: string]: unknown;
}

export interface BaseLineChartProps {
  data: object[];
  title?: string;
  series: LineDataSeries[];
  colorPalette?: 'line' | 'pie' | 'status';
  useThemeColors?: boolean;
  height?: number;
  xAxisDataKey?: string;
  showGrid?: boolean;
  legendProps?: Record<string, unknown>;
  tooltipProps?: Record<string, unknown>;
  elevation?: number;
  preventLegendOverflow?: boolean;
  variant?: 'dashboard' | 'test-results';
  yAxisConfig?: {
    domain?: [number, number];
    allowDataOverflow?: boolean;
    tickCount?: number;
    tickFormatter?: (value: number) => string;
  };
}

// Utility functions for chart data handling
export const chartUtils = {
  /**
   * Gets the last N months as data points
   */
  getLastNMonths: (count = 6): MonthDataPoint[] => {
    const today = new Date();
    return Array(count)
      .fill(0)
      .map((_, i) => {
        const date = subMonths(today, count - 1 - i); // Start from (count-1) months ago to current month
        return {
          name: format(date, 'MMM'),
          date,
          tests: 0,
          passed: 0,
          total: 0,
          monthKey: format(date, 'yyyy-MM'), // Add monthKey for mapping with API data
        };
      });
  },

  /**
   * Creates monthly data from API response
   */
  createMonthlyData: (
    monthlyCounts: Record<string, number>,
    baseDataPoints: MonthDataPoint[] = chartUtils.getLastNMonths()
  ): MonthDataPoint[] => {
    return baseDataPoints.map(month => ({
      ...month,
      total: monthlyCounts[month.monthKey] || 0,
    }));
  },

  /**
   * Calculates the appropriate y-axis domain based on data values
   */
  calculateYAxisDomain: (
    data: { [key: string]: number }[],
    valueKey = 'value'
  ): [number, number] => {
    if (!data.length) return [0, 100];

    // Find the maximum value
    const maxValue = Math.max(
      ...data.map(item =>
        typeof item[valueKey] === 'number' ? item[valueKey] : 0
      )
    );

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

    const upperBound = Math.ceil((maxValue * multiplier) / 10) * 10;

    return [0, upperBound];
  },

  /**
   * Calculates optimal Y-axis width based on data values and series configuration
   */
  calculateYAxisWidth: (
    data: object[],
    series: LineDataSeries[],
    yAxisConfig?: { tickFormatter?: (value: number) => string }
  ): number => {
    if (!data.length || !series.length) return 25; // Minimum width for empty data

    // Find all numeric values across all series
    const allValues: number[] = [];

    data.forEach(item => {
      series.forEach(s => {
        const value = (item as Record<string, unknown>)[s.dataKey];
        if (typeof value === 'number' && !isNaN(value)) {
          allValues.push(value);
        }
      });
    });

    if (allValues.length === 0) return 25;

    // Find the maximum value to determine required width
    const maxValue = Math.max(...allValues);
    const minValue = Math.min(...allValues);

    // Use custom formatter if provided, otherwise use default formatting
    const formatValue =
      yAxisConfig?.tickFormatter || ((value: number) => value.toString());

    // Format the extreme values to see their string length
    const maxValueStr = formatValue(maxValue);
    const minValueStr = formatValue(minValue);

    // Find the longest formatted string
    const maxLength = Math.max(maxValueStr.length, minValueStr.length);

    // Calculate width based on character count
    // Approximate: 8px per character + 10px padding
    const calculatedWidth = maxLength * 8 + 10;

    // Ensure minimum and maximum bounds
    return Math.max(20, Math.min(calculatedWidth, 60));
  },
};

export default function BaseLineChart({
  data,
  title,
  series,
  colorPalette = 'line',
  useThemeColors = true,
  height: _height = 180,
  xAxisDataKey = 'name',
  showGrid = true,
  legendProps,
  tooltipProps,
  elevation = 2,
  preventLegendOverflow = false,
  variant = 'dashboard',
  yAxisConfig,
}: BaseLineChartProps) {
  const theme = useTheme();

  // Convert rem to pixels for Recharts (assuming 1rem = 16px)
  const getPixelFontSize = (remSize: string | number | undefined): number => {
    if (!remSize) return 10; // fallback size
    const remValue = parseFloat(String(remSize));
    return remValue * 16;
  };

  // Update legend props to use theme
  const defaultLegendProps = {
    wrapperStyle: { fontSize: theme.typography.chartTick.fontSize },
    iconSize: 8,
  };
  const themedLegendProps = {
    ...defaultLegendProps,
    ...(legendProps && typeof legendProps === 'object' ? legendProps : {}),
    wrapperStyle: {
      ...defaultLegendProps.wrapperStyle,
      ...(legendProps &&
      typeof legendProps === 'object' &&
      legendProps.wrapperStyle
        ? legendProps.wrapperStyle
        : {}),
      fontSize: theme.typography.chartTick.fontSize,
    },
  };

  // Default tooltip props with theme awareness
  const defaultTooltipProps = {
    contentStyle: {
      fontSize: theme.typography.chartTick.fontSize,
      backgroundColor: theme.palette.background.paper,
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: '4px',
    },
    itemStyle: {
      color: theme.palette.text.primary,
    },
    labelStyle: {
      color: theme.palette.text.primary,
    },
  };

  const finalTooltipProps = tooltipProps || defaultTooltipProps;
  const defaultColors = theme.chartPalettes.line;

  // Calculate optimal Y-axis width based on data (dashboard optimization)
  const yAxisWidth =
    variant === 'dashboard'
      ? chartUtils.calculateYAxisWidth(data, series, yAxisConfig)
      : 50; // Fixed width for test-results variant

  const chartContent = (
    <>
      {title && (
        <Typography
          variant="subtitle2"
          sx={{ mb: 1, px: 0.5, textAlign: 'center' }}
        >
          {title}
        </Typography>
      )}
      <Box className={styles.chartContainer}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{
              top: variant === 'dashboard' ? 2 : 5, // Dashboard: minimal top margin for max grid space
              right: preventLegendOverflow
                ? 15
                : variant === 'dashboard'
                  ? 2
                  : 5, // Dashboard: minimal right margin
              bottom: preventLegendOverflow
                ? 25
                : variant === 'dashboard'
                  ? 18
                  : 2, // Dashboard: tight bottom for legend
              left: variant === 'dashboard' ? -5 : 0, // Dashboard: negative left to maximize grid width
            }}
          >
            {showGrid && <CartesianGrid strokeDasharray="3 3" />}
            <XAxis
              dataKey={xAxisDataKey}
              tick={{
                fontSize: getPixelFontSize(theme.typography.chartTick.fontSize),
                fill: theme.palette.text.primary,
              }}
              axisLine={{ strokeWidth: 1 }}
              tickLine={{ strokeWidth: 1 }}
            />
            <YAxis
              tick={{
                fontSize: getPixelFontSize(theme.typography.chartTick.fontSize),
                fill: theme.palette.text.primary,
              }}
              axisLine={{ strokeWidth: 1 }}
              tickLine={{ strokeWidth: 1 }}
              width={yAxisWidth}
              {...yAxisConfig}
            />
            <Tooltip {...finalTooltipProps} />
            <Legend
              {...themedLegendProps}
              height={variant === 'dashboard' ? 16 : 20}
            />
            {series.map((s, index) => (
              <Line
                key={index}
                type="monotone"
                dataKey={s.dataKey}
                name={s.name || s.dataKey}
                stroke={
                  s.color ||
                  (useThemeColors
                    ? theme.chartPalettes[colorPalette][
                        index % theme.chartPalettes[colorPalette].length
                      ]
                    : defaultColors[index % defaultColors.length])
                }
                strokeWidth={s.strokeWidth || 1.5}
                dot={{ strokeWidth: 1, r: 3 }}
                activeDot={{ r: 5, strokeWidth: 1 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Box>
    </>
  );

  // If elevation is 0, render content without Card wrapper
  if (elevation === 0) {
    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-start',
          p: 0.5,
        }}
      >
        {chartContent}
      </Box>
    );
  }

  // Otherwise, render with Card wrapper
  return (
    <Card className={styles.card} elevation={elevation}>
      <CardContent className={styles.cardContent}>{chartContent}</CardContent>
    </Card>
  );
}
