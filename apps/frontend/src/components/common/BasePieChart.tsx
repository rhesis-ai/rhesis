/* eslint-disable react/no-array-index-key -- Pie chart cell rendering */

import React, { useMemo, useCallback } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Typography, Box, Card, CardContent, useTheme } from '@mui/material';
import { useChartColors } from '../layout/BaseChartColors';

// Constants to replace magic numbers
const CHART_CONSTANTS = {
  FULL_CIRCLE: 360,
  BOTTOM_AREA_START: 225,
  BOTTOM_AREA_END: 315,
  LABEL_RADIUS_MULTIPLIER: {
    BOTTOM: 1.2,
    NORMAL: 1.35,
  },
  LABEL_LINE_RADIUS_MULTIPLIER: {
    BOTTOM: 1.15,
    NORMAL: 1.3,
  },
  MIN_PERCENTAGE_THRESHOLD: 0.05,
  RADIAN: Math.PI / 180,
  LEGEND_HEIGHT: 20,
} as const;

// Type definitions for better type safety
interface LabelProps {
  cx: number;
  cy: number;
  midAngle: number;
  innerRadius: number;
  outerRadius: number;
  percent: number;
  index: number;
  name: string;
}

interface LabelLineProps {
  cx: number;
  cy: number;
  midAngle: number;
  outerRadius: number;
}

interface DataItem {
  name: string;
  value: number;
  fullName?: string;
  percentage?: string;
}

export interface BasePieChartProps {
  data: DataItem[];
  title?: string;
  colors?: string[];
  colorPalette?: 'pie' | 'status' | 'line';
  useThemeColors?: boolean;
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
  showPercentage?: boolean;
  legendProps?: Record<string, any>;
  tooltipProps?: Record<string, any>;
  elevation?: number;
  preventLegendOverflow?: boolean;
  variant?: 'dashboard' | 'test-results';
}

// Utility functions for pie chart data handling
export const pieChartUtils = {
  /**
   * Truncates long names for legends
   */
  truncateName: (name: string, maxLength = 15): string => {
    if (name.length <= maxLength) return name;
    return `${name.substring(0, maxLength - 3)}...`;
  },

  /**
   * Generates a title for a dimension
   */
  generateDimensionTitle: (dimension: string): string => {
    // Convert camelCase or snake_case to Title Case
    const formatted = dimension
      .replace(/([A-Z])/g, ' $1') // Convert camelCase to space separated
      .replace(/_/g, ' ') // Convert snake_case to space separated
      .toLowerCase()
      .trim();

    // Capitalize first letter of each word
    return `Tests by ${formatted
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')}`;
  },

  /**
   * Generates pie chart data from a breakdown object
   */
  generateDimensionData: (
    breakdown: Record<string, number> | undefined,
    total: number,
    top = 5,
    fallbackData = [{ name: 'Loading...', value: 100 }]
  ): DataItem[] => {
    if (!breakdown) return fallbackData;

    // Sort by value in descending order to show most significant values first
    return Object.entries(breakdown)
      .sort((a, b) => b[1] - a[1])
      .slice(0, top)
      .map(([name, value]) => {
        // Calculate percentage for display
        const percentage = ((value / total) * 100).toFixed(1);
        return {
          name: pieChartUtils.truncateName(name),
          value,
          fullName: name, // Keep the full name for tooltips
          percentage: `${percentage}%`, // Add percentage for tooltip
        };
      });
  },

  /**
   * Validates component props
   */
  validateProps: (props: BasePieChartProps): void => {
    if (props.data.length === 0) {
    }
    if (props.height && props.height <= 0) {
    }
    if (
      props.innerRadius &&
      props.outerRadius &&
      props.innerRadius >= props.outerRadius
    ) {
    }
  },
};

// Helper function to check if angle is in bottom area
const isInBottomArea = (angle: number): boolean => {
  const normalizedAngle =
    ((angle % CHART_CONSTANTS.FULL_CIRCLE) + CHART_CONSTANTS.FULL_CIRCLE) %
    CHART_CONSTANTS.FULL_CIRCLE;
  return (
    normalizedAngle >= CHART_CONSTANTS.BOTTOM_AREA_START &&
    normalizedAngle <= CHART_CONSTANTS.BOTTOM_AREA_END
  );
};

// Custom label rendering function factory - accepts theme color and font size
const createCustomizedLabel = (
  chartLabelFontSize: string,
  textColor: string
) => {
  const CustomizedLabel = ({
    cx,
    cy,
    midAngle,
    innerRadius: _innerRadius,
    outerRadius,
    percent,
    index: _index,
    name,
  }: LabelProps) => {
    // Only show labels for segments with significant percentage (helps prevent overlap)
    if (percent < CHART_CONSTANTS.MIN_PERCENTAGE_THRESHOLD) return null;

    // Check if the label would be in the bottom area where legend is positioned
    const isBottomArea = isInBottomArea(midAngle);

    // Adjust radius based on position to avoid legend overlap
    const radius = isBottomArea
      ? outerRadius * CHART_CONSTANTS.LABEL_RADIUS_MULTIPLIER.BOTTOM
      : outerRadius * CHART_CONSTANTS.LABEL_RADIUS_MULTIPLIER.NORMAL;

    const x = cx + radius * Math.cos(-midAngle * CHART_CONSTANTS.RADIAN);
    const y = cy + radius * Math.sin(-midAngle * CHART_CONSTANTS.RADIAN);

    // Determine if the label is on the right side or left side of the chart
    const isRightSide = x > cx;

    return (
      <text
        x={x}
        y={y}
        fill={textColor}
        textAnchor={isRightSide ? 'start' : 'end'}
        dominantBaseline="central"
        fontSize={chartLabelFontSize}
        fontWeight="bold"
        aria-label={`${(percent * 100).toFixed(0)}% of ${name}`}
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  CustomizedLabel.displayName = 'CustomizedLabel';
  return CustomizedLabel;
};

// Custom label line rendering function
const renderCustomizedLabelLine = ({
  cx,
  cy,
  midAngle,
  outerRadius,
}: LabelLineProps) => {
  // Check if the label would be in the bottom area where legend is positioned
  const isBottomArea = isInBottomArea(midAngle);

  // Adjust end radius based on position to match label positioning
  const startRadius = outerRadius + 2;
  const endRadius = isBottomArea
    ? outerRadius * CHART_CONSTANTS.LABEL_LINE_RADIUS_MULTIPLIER.BOTTOM
    : outerRadius * CHART_CONSTANTS.LABEL_LINE_RADIUS_MULTIPLIER.NORMAL;

  const x1 = cx + startRadius * Math.cos(-midAngle * CHART_CONSTANTS.RADIAN);
  const y1 = cy + startRadius * Math.sin(-midAngle * CHART_CONSTANTS.RADIAN);
  const x2 = cx + endRadius * Math.cos(-midAngle * CHART_CONSTANTS.RADIAN);
  const y2 = cy + endRadius * Math.sin(-midAngle * CHART_CONSTANTS.RADIAN);

  return <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#ccc" strokeWidth={1} />;
};

export default function BasePieChart({
  data,
  title,
  colors,
  colorPalette = 'pie',
  useThemeColors = true,
  height = 200,
  innerRadius = 30,
  outerRadius = 55,
  showPercentage = true,
  legendProps,
  tooltipProps,
  elevation = 2,
  preventLegendOverflow = false,
  variant: _variant = 'dashboard',
}: BasePieChartProps) {
  // Validate props in development
  if (process.env.FRONTEND_ENV === 'development') {
    pieChartUtils.validateProps({
      data,
      title,
      colors,
      colorPalette,
      useThemeColors,
      height,
      innerRadius,
      outerRadius,
      showPercentage,
      legendProps,
      tooltipProps,
    });
  }

  // Get theme colors
  const theme = useTheme();

  const { palettes } = useChartColors();

  // Default tooltip props with theme awareness
  const defaultTooltipProps = useMemo(
    () => ({
      contentStyle: {
        fontSize: String(theme.typography.chartTick.fontSize),
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
    }),
    [theme]
  );

  const finalTooltipProps = tooltipProps || defaultTooltipProps;

  // Memoize chart colors calculation
  const chartColors = useMemo(() => {
    const defaultColors = theme.chartPalettes.pie;
    return (
      colors ||
      (useThemeColors ? palettes[colorPalette] || defaultColors : defaultColors)
    );
  }, [colors, useThemeColors, palettes, colorPalette, theme.chartPalettes.pie]);

  // Memoize chart dimensions calculation
  const chartDimensions = useMemo(() => {
    const adjustedHeight = height + CHART_CONSTANTS.LEGEND_HEIGHT;
    const chartHeight = height - (showPercentage ? 5 : 3);
    const cyPercentage = (chartHeight / adjustedHeight) * 50;

    return {
      adjustedHeight,
      chartHeight,
      cyPercentage,
    };
  }, [height, showPercentage]);

  // Memoize enhanced legend props
  const enhancedLegendProps = useMemo(() => {
    const defaultLegendProps = {
      wrapperStyle: {
        fontSize: String(theme.typography.chartTick.fontSize),
        marginTop: theme.spacing(0.625),
        marginBottom: theme.spacing(0),
        paddingBottom: '2px',
      },
      verticalAlign: 'bottom' as const,
      align: 'center' as const,
    };

    return {
      ...defaultLegendProps,
      ...legendProps,
      wrapperStyle: {
        ...defaultLegendProps.wrapperStyle,
        ...legendProps?.wrapperStyle,
        marginTop: theme.spacing(0.625),
        marginBottom: theme.spacing(0),
        paddingBottom: '2px',
      },
    };
  }, [legendProps, theme]);

  // Create customized label function with theme access
  const renderCustomizedLabel = useMemo(
    () =>
      createCustomizedLabel(
        String(theme.typography.chartLabel.fontSize),
        theme.palette.text.primary
      ),
    [theme.typography.chartLabel.fontSize, theme.palette.text.primary]
  );

  // Memoize data lookup for better tooltip performance
  const dataLookup = useMemo(() => {
    return new Map(data.map(item => [item.name, item]));
  }, [data]);

  // Optimized tooltip formatter
  const tooltipFormatter = useCallback(
    (value: any, name: any) => {
      const item = dataLookup.get(name);
      return [value, item?.fullName || name];
    },
    [dataLookup]
  );

  const chartContent = (
    <>
      {title && (
        <Typography
          variant="subtitle2"
          sx={{ mb: 1, px: 0.5, textAlign: 'center' }}
          component="h3"
          role="heading"
          aria-level={3}
        >
          {title}
        </Typography>
      )}
      <Box
        sx={{
          flexGrow: 1,
          display: 'flex',
          alignItems: 'stretch',
          justifyContent: 'center',
        }}
      >
        <ResponsiveContainer
          width="100%"
          height={chartDimensions.adjustedHeight}
        >
          <PieChart
            margin={{
              top: 5,
              right: 5,
              bottom: preventLegendOverflow ? 60 : 5,
              left: 0,
            }}
            height={chartDimensions.adjustedHeight}
          >
            <Pie
              data={data}
              cx="50%"
              cy={`${chartDimensions.cyPercentage}%`}
              innerRadius={innerRadius}
              outerRadius={outerRadius}
              paddingAngle={2}
              fill={chartColors[0]}
              dataKey="value"
              label={showPercentage ? renderCustomizedLabel : undefined}
              labelLine={showPercentage ? renderCustomizedLabelLine : false}
            >
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={chartColors[index % chartColors.length]}
                />
              ))}
            </Pie>
            <Tooltip {...finalTooltipProps} formatter={tooltipFormatter} />
            <Legend {...enhancedLegendProps} />
          </PieChart>
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
          p: 0.5,
          '&:last-child': { pb: 0.25 },
        }}
      >
        {chartContent}
      </Box>
    );
  }

  // Otherwise, render with Card wrapper
  return (
    <Card sx={{ height: '100%' }} elevation={elevation}>
      <CardContent
        sx={{
          p: 0.5,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          '&:last-child': { pb: 0.25 },
        }}
      >
        {chartContent}
      </CardContent>
    </Card>
  );
}
