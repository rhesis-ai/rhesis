import React, { useMemo } from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Typography, Box, Card, CardContent, useTheme } from '@mui/material';
import { useChartColors } from '../layout/BaseChartColors';
import styles from '@/styles/BaseLineChart.module.css'; // Reuse existing styles

export interface ScatterDataPoint {
  x: number | string;
  y: number;
  name?: string;
  isHighlighted?: boolean;
  [key: string]: unknown;
}

export interface BaseScatterChartProps {
  data: ScatterDataPoint[];
  title?: string;
  colorPalette?: 'line' | 'pie' | 'status';
  useThemeColors?: boolean;
  height?: number;
  xAxisLabel?: string;
  yAxisLabel?: string;
  showGrid?: boolean;
  legendProps?: Record<string, unknown>;
  tooltipProps?: Record<string, unknown>;
  yAxisConfig?: {
    domain?: [number, number];
    allowDataOverflow?: boolean;
    tickCount?: number;
    tickFormatter?: (value: number) => string;
  };
  xAxisConfig?: {
    domain?: [number, number] | ['auto', 'auto'];
    allowDataOverflow?: boolean;
    tickCount?: number;
    tickFormatter?: (value: string | number) => string;
  };
  highlightedColor?: string;
  normalColor?: string;
}

// Utility functions for scatter chart data handling
export const scatterChartUtils = {
  /**
   * Calculates optimal Y-axis width based on scatter data values
   */
  calculateYAxisWidth: (
    data: ScatterDataPoint[],
    yAxisConfig?: { tickFormatter?: (value: number) => string }
  ): number => {
    if (!data.length) return 25; // Minimum width for empty data

    // Find all Y values
    const yValues = data
      .map(item => item.y)
      .filter(value => typeof value === 'number' && !isNaN(value));

    if (yValues.length === 0) return 25;

    // Find the maximum and minimum values to determine required width
    const maxValue = Math.max(...yValues);
    const minValue = Math.min(...yValues);

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

export default function BaseScatterChart({
  data,
  title,
  colorPalette = 'line',
  useThemeColors = true,
  height = 180,
  xAxisLabel,
  yAxisLabel,
  showGrid = true,
  legendProps,
  tooltipProps,
  yAxisConfig,
  xAxisConfig,
  highlightedColor,
  normalColor,
}: BaseScatterChartProps) {
  const theme = useTheme();

  // Convert rem to pixels for Recharts (assuming 1rem = 16px)
  const getPixelFontSize = (remSize: string): number => {
    const remValue = parseFloat(remSize);
    return remValue * 16;
  };

  // Update legend props to use theme
  const defaultLegendProps = {
    wrapperStyle: { fontSize: String(theme.typography.chartTick.fontSize) },
    iconSize: 8,
  };
  const _themedLegendProps = {
    ...defaultLegendProps,
    ...(legendProps && typeof legendProps === 'object' ? legendProps : {}),
    wrapperStyle: {
      ...defaultLegendProps.wrapperStyle,
      ...(legendProps &&
      typeof legendProps === 'object' &&
      legendProps.wrapperStyle
        ? legendProps.wrapperStyle
        : {}),
      fontSize: String(theme.typography.chartTick.fontSize),
    },
  };
  const { palettes } = useChartColors();

  // Default tooltip props with theme awareness
  const defaultTooltipProps = {
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
  };

  const finalTooltipProps = tooltipProps || defaultTooltipProps;

  // Calculate optimal Y-axis width based on data
  const yAxisWidth = scatterChartUtils.calculateYAxisWidth(data, yAxisConfig);

  // Get colors from theme or use defaults
  const chartColors = useMemo(() => {
    const defaultColors = theme.chartPalettes.line;
    return useThemeColors
      ? palettes[colorPalette] || defaultColors
      : defaultColors;
  }, [useThemeColors, palettes, colorPalette, theme.chartPalettes.line]);

  const finalHighlightedColor = highlightedColor || chartColors[0];
  const finalNormalColor =
    normalColor || chartColors[1] || theme.palette.action.disabled;

  // Custom dot component to handle highlighting
  const CustomDot = (props: Record<string, unknown>) => {
    const { cx, cy, payload } = props as {
      cx?: number;
      cy?: number;
      payload?: ScatterDataPoint;
    };
    const isHighlighted = payload?.isHighlighted;

    return (
      <circle
        cx={cx}
        cy={cy}
        r={isHighlighted ? 6 : 4}
        fill={isHighlighted ? finalHighlightedColor : finalNormalColor}
        stroke={isHighlighted ? finalHighlightedColor : finalNormalColor}
        strokeWidth={isHighlighted ? 2 : 1}
        opacity={0.8}
      />
    );
  };

  // Custom tooltip formatter
  const customTooltipFormatter = (
    value: string | number,
    name: string,
    props: { payload?: unknown }
  ) => {
    const { payload: _payload } = props;
    if (name === 'y') {
      return [`${value}%`, 'Pass Rate'];
    }
    return [value, name];
  };

  const customTooltipLabelFormatter = (
    label: string | number,
    payload: Array<{ payload?: ScatterDataPoint }>
  ) => {
    if (payload && payload.length > 0) {
      const firstPayload = payload[0];
      const data = firstPayload?.payload;
      return data?.name || `Run ${label}`;
    }
    return label;
  };

  return (
    <Card className={styles.card} elevation={2}>
      <CardContent className={styles.cardContent}>
        {title && (
          <Typography
            variant="subtitle2"
            sx={{ mb: 1, px: 0.5, textAlign: 'center' }}
          >
            {title}
          </Typography>
        )}
        <Box className={styles.chartContainer}>
          <ResponsiveContainer width="100%" height={height}>
            <ScatterChart
              data={data}
              margin={{ top: 5, right: 5, bottom: 15, left: 0 }}
            >
              {showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis
                dataKey="x"
                type="number"
                tick={{
                  fontSize: getPixelFontSize(
                    String(theme.typography.chartTick.fontSize)
                  ),
                  fill: theme.palette.text.primary,
                }}
                axisLine={{ strokeWidth: 1 }}
                tickLine={{ strokeWidth: 1 }}
                label={
                  xAxisLabel
                    ? {
                        value: xAxisLabel,
                        position: 'insideBottom',
                        offset: -10,
                        style: {
                          fontSize: String(theme.typography.chartTick.fontSize),
                        },
                      }
                    : undefined
                }
                {...xAxisConfig}
              />
              <YAxis
                dataKey="y"
                type="number"
                tick={{
                  fontSize: getPixelFontSize(
                    String(theme.typography.chartTick.fontSize)
                  ),
                  fill: theme.palette.text.primary,
                }}
                axisLine={{ strokeWidth: 1 }}
                tickLine={{ strokeWidth: 1 }}
                width={yAxisWidth}
                label={
                  yAxisLabel
                    ? {
                        value: yAxisLabel,
                        angle: -90,
                        position: 'insideLeft',
                        style: {
                          fontSize: String(theme.typography.chartTick.fontSize),
                        },
                      }
                    : undefined
                }
                {...yAxisConfig}
              />
              <Tooltip
                {...finalTooltipProps}
                formatter={customTooltipFormatter}
                labelFormatter={customTooltipLabelFormatter}
              />
              <Scatter
                dataKey="y"
                fill={finalNormalColor}
                shape={<CustomDot />}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </Box>
      </CardContent>
    </Card>
  );
}
