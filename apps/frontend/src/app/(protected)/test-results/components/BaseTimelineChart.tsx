'use client';

import React, { useMemo } from 'react';
import {
  Paper,
  Typography,
  CircularProgress,
  Alert,
  Box,
  useTheme,
} from '@mui/material';
import { BaseLineChart } from '@/components/common/BaseCharts';
import {
  TimelineDataItem,
  PassFailData,
  ChartDataPoint,
  transformTimelineData,
  generateMockTimelineData,
} from './timelineUtils';

export interface BaseTimelineChartProps {
  title: string;
  data: TimelineDataItem[];
  dataExtractor: (item: TimelineDataItem) => PassFailData | null;
  height?: number;
  contextInfo?: string | ((data: ChartDataPoint[]) => string);
  showMockDataFallback?: boolean;
  filterEmptyData?: boolean;
  isLoading?: boolean;
  error?: string | null;
  titleVariant?: 'h6' | 'h5' | 'h4';
  titleFontSize?: string;
  subtitleFontSize?: string;
}

export default function BaseTimelineChart({
  title,
  data,
  dataExtractor,
  height = 400,
  contextInfo,
  showMockDataFallback = false,
  filterEmptyData = false,
  isLoading = false,
  error = null,
  titleVariant = 'h6',
  titleFontSize,
  subtitleFontSize,
}: BaseTimelineChartProps) {
  const theme = useTheme();

  // Use a consistent blue color for pass rates that works in both light and dark themes
  // This matches the first color in the theme's line chart palette
  const passRateColor = theme.chartPalettes.line[0]; // Primary blue from theme

  const chartData = useMemo(() => {
    const transformedData = transformTimelineData(
      data,
      dataExtractor,
      filterEmptyData
    );

    // If no data and mock fallback is enabled, return mock data
    if (transformedData.length === 0 && showMockDataFallback) {
      return generateMockTimelineData();
    }

    return transformedData;
  }, [data, dataExtractor, filterEmptyData, showMockDataFallback]);

  const getContextInfo = (): string => {
    if (typeof contextInfo === 'string') {
      return contextInfo;
    }

    if (typeof contextInfo === 'function') {
      return contextInfo(chartData);
    }

    // Default context info
    if (chartData.length === 0) {
      return 'No data available for the selected period';
    }

    const totalTests = chartData.reduce((sum, item) => sum + item.total, 0);
    return `${chartData.length} data points, ${totalTests} total tests`;
  };

  // Loading state
  if (isLoading) {
    return (
      <Paper
        elevation={theme.elevation.standard}
        sx={{
          p: theme.customSpacing.container.medium,
          height,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Typography
          variant={titleVariant}
          sx={{
            mb: theme.customSpacing.section.small,
            fontSize: titleFontSize,
          }}
        >
          {title}
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            mb: theme.customSpacing.section.small,
            fontSize: subtitleFontSize,
          }}
        >
          {typeof contextInfo === 'string'
            ? contextInfo
            : 'Loading timeline data...'}
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
            Loading timeline...
          </Typography>
        </Box>
      </Paper>
    );
  }

  // Error state
  if (error) {
    return (
      <Paper
        elevation={theme.elevation.standard}
        sx={{
          p: theme.customSpacing.container.medium,
          height,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Typography
          variant={titleVariant}
          sx={{
            mb: theme.customSpacing.section.small,
            fontSize: titleFontSize,
          }}
        >
          {title}
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            mb: theme.customSpacing.section.small,
            fontSize: subtitleFontSize,
          }}
        >
          Error occurred
        </Typography>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  // No data state
  if (chartData.length === 0) {
    return (
      <Paper
        elevation={theme.elevation.standard}
        sx={{
          p: theme.customSpacing.container.medium,
          height,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Typography
          variant={titleVariant}
          sx={{
            mb: theme.customSpacing.section.small,
            fontSize: titleFontSize,
          }}
        >
          {title}
        </Typography>
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            mb: theme.customSpacing.section.small,
            fontSize: subtitleFontSize,
          }}
        >
          {getContextInfo()}
        </Typography>
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            color: 'text.secondary',
          }}
        >
          <Typography variant="body2">
            No test results for this period
          </Typography>
        </Box>
      </Paper>
    );
  }

  // Chart with data
  return (
    <Paper
      elevation={theme.elevation.standard}
      sx={{
        p: theme.customSpacing.container.medium,
        height,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Typography
        variant={titleVariant}
        sx={{ mb: theme.customSpacing.section.small, fontSize: titleFontSize }}
      >
        {title}
      </Typography>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{
          mb: theme.customSpacing.section.small,
          fontSize: subtitleFontSize,
          minHeight: '2.5rem', // Ensure consistent height for 2 lines
          display: 'flex',
          alignItems: 'flex-start',
        }}
      >
        {getContextInfo()}
      </Typography>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <BaseLineChart
          title=""
          data={chartData}
          series={[
            {
              dataKey: 'pass_rate',
              name: 'Pass Rate (%)',
              color: passRateColor, // Use consistent blue color for pass rates
            },
          ]}
          useThemeColors={false} // Disable automatic theme colors since we're specifying manually
          colorPalette="line"
          height={height - 130} // Account for title/subtitle space and legend overflow
          elevation={0}
          preventLegendOverflow={true}
          variant="test-results"
          yAxisConfig={{
            domain: [0, 100],
            allowDataOverflow: false,
            tickCount: height > 350 ? 6 : 5,
            tickFormatter: (value: number) => `${value}%`,
          }}
        />
      </Box>
    </Paper>
  );
}
