import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
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
  [key: string]: any;
}

export interface BaseLineChartProps {
  data: Record<string, any>[];
  title?: string;
  series: LineDataSeries[];
  colorPalette?: 'line' | 'pie' | 'status';
  useThemeColors?: boolean;
  height?: number;
  xAxisDataKey?: string;
  showGrid?: boolean;
  legendProps?: Record<string, any>;
  tooltipProps?: Record<string, any>;
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
    return Array(count).fill(0).map((_, i) => {
      const date = subMonths(today, (count - 1) - i); // Start from (count-1) months ago to current month
      return {
        name: format(date, 'MMM'),
        date,
        tests: 0,
        passed: 0,
        total: 0,
        monthKey: format(date, 'yyyy-MM') // Add monthKey for mapping with API data
      };
    });
  },

  /**
   * Creates monthly data from API response
   */
  createMonthlyData: (monthlyCounts: Record<string, number>, baseDataPoints: MonthDataPoint[] = chartUtils.getLastNMonths()): MonthDataPoint[] => {
    return baseDataPoints.map(month => ({
      ...month,
      total: monthlyCounts[month.monthKey] || 0
    }));
  },

  /**
   * Calculates the appropriate y-axis domain based on data values
   */
  calculateYAxisDomain: (data: { [key: string]: number }[], valueKey = 'value'): [number, number] => {
    if (!data.length) return [0, 100];
    
    // Find the maximum value
    const maxValue = Math.max(...data.map(item => 
      typeof item[valueKey] === 'number' ? item[valueKey] : 0
    ));
    
    // Round up to the nearest nice value for the upper bound
    // Using a multiplier approach to make the chart look better
    const multiplier = 
      maxValue <= 10 ? 2 :     // For small values, double it
      maxValue <= 100 ? 1.5 :  // For medium values, add 50%
      maxValue <= 1000 ? 1.2 : // For larger values, add 20%
      1.1;                     // For very large values, add 10%
    
    const upperBound = Math.ceil(maxValue * multiplier / 10) * 10;
    
    return [0, upperBound];
  }
};

export default function BaseLineChart({
  data,
  title,
  series,
  colorPalette = 'line',
  useThemeColors = true,
  height = 150,
  xAxisDataKey = 'name',
  showGrid = true,
  legendProps = { wrapperStyle: { fontSize: '10px' }, iconSize: 8 },
  tooltipProps,
  yAxisConfig
}: BaseLineChartProps) {
  const theme = useTheme();

  // Default tooltip props with theme awareness
  const defaultTooltipProps = {
    contentStyle: { 
      fontSize: '10px',
      backgroundColor: theme.palette.background.paper,
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: '4px',
      color: theme.palette.text.primary
    }
  };

  const finalTooltipProps = tooltipProps || defaultTooltipProps;
  const defaultColors = ['#8884d8', '#82ca9d', '#ffc658', '#ff8042'];
  
  return (
    <Card className={styles.card} elevation={2}>
      <CardContent className={styles.cardContent}>
        {title && (
          <Typography variant="subtitle1" className={styles.title}>
            {title}
          </Typography>
        )}
        <Box className={styles.chartContainer}>
          <ResponsiveContainer width="100%" height={height}>
            <LineChart 
              data={data} 
              margin={{ top: 30, right: 15, bottom: 5, left: -15 }}
            >
              {showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis 
                dataKey={xAxisDataKey} 
                tick={{ fontSize: 10 }}
                axisLine={{ strokeWidth: 1 }}
                tickLine={{ strokeWidth: 1 }}
              />
              <YAxis 
                tick={{ fontSize: 10 }} 
                axisLine={{ strokeWidth: 1 }}
                tickLine={{ strokeWidth: 1 }}
                {...yAxisConfig}
              />
              <Tooltip {...finalTooltipProps} />
              <Legend {...legendProps} height={30} />
              {series.map((s, index) => (
                <Line
                  key={index}
                  type="monotone"
                  dataKey={s.dataKey}
                  name={s.name || s.dataKey}
                  stroke={s.color || (useThemeColors ? theme.chartPalettes[colorPalette][index % theme.chartPalettes[colorPalette].length] : defaultColors[index % defaultColors.length])}
                  strokeWidth={s.strokeWidth || 1.5}
                  dot={{ strokeWidth: 1, r: 3 }}
                  activeDot={{ r: 5, strokeWidth: 1 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </Box>
      </CardContent>
    </Card>
  );
} 