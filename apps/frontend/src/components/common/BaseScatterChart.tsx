import React, { useMemo } from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell
} from 'recharts';
import { Typography, Box, Card, CardContent, useTheme } from '@mui/material';
import { useChartColors } from '../layout/BaseChartColors';
import styles from '@/styles/BaseLineChart.module.css'; // Reuse existing styles

export interface ScatterDataPoint {
  x: number | string;
  y: number;
  name?: string;
  isHighlighted?: boolean;
  [key: string]: any;
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
  legendProps?: Record<string, any>;
  tooltipProps?: Record<string, any>;
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
    tickFormatter?: (value: any) => string;
  };
  highlightedColor?: string;
  normalColor?: string;
}

export default function BaseScatterChart({
  data,
  title,
  colorPalette = 'line',
  useThemeColors = true,
  height = 180,
  xAxisLabel,
  yAxisLabel,
  showGrid = true,
  legendProps = { wrapperStyle: { fontSize: '10px' }, iconSize: 8 },
  tooltipProps,
  yAxisConfig,
  xAxisConfig,
  highlightedColor,
  normalColor
}: BaseScatterChartProps) {
  const theme = useTheme();
  
  // Convert rem to pixels for Recharts (assuming 1rem = 16px)
  const getPixelFontSize = (remSize: string): number => {
    const remValue = parseFloat(remSize);
    return remValue * 16;
  };
  
  // Update legend props to use theme
  const themedLegendProps = {
    ...legendProps,
    wrapperStyle: {
      ...legendProps.wrapperStyle,
      fontSize: theme.typography.chartTick.fontSize
    }
  };
  const { palettes } = useChartColors();

  // Default tooltip props with theme awareness
  const defaultTooltipProps = {
    contentStyle: { 
      fontSize: theme.typography.chartTick.fontSize,
      backgroundColor: theme.palette.background.paper,
      border: `1px solid ${theme.palette.divider}`,
      borderRadius: '4px',
      color: theme.palette.text.primary
    }
  };

  const finalTooltipProps = tooltipProps || defaultTooltipProps;
  
  // Get colors from theme or use defaults
  const chartColors = useMemo(() => {
    const defaultColors = ['#8884d8', '#82ca9d', '#ffc658', '#ff8042'];
    return useThemeColors ? (palettes[colorPalette] || defaultColors) : defaultColors;
  }, [useThemeColors, palettes, colorPalette]);

  const finalHighlightedColor = highlightedColor || chartColors[0];
  const finalNormalColor = normalColor || chartColors[1] || '#cccccc';

  // Custom dot component to handle highlighting
  const CustomDot = (props: any) => {
    const { cx, cy, payload } = props;
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
  const customTooltipFormatter = (value: any, name: string, props: any) => {
    const { payload } = props;
    if (name === 'y') {
      return [`${value}%`, 'Pass Rate'];
    }
    return [value, name];
  };

  const customTooltipLabelFormatter = (label: any, payload: any) => {
    if (payload && payload.length > 0) {
      const data = payload[0].payload;
      return data.name || `Run ${label}`;
    }
    return label;
  };

  return (
    <Card className={styles.card} elevation={2}>
      <CardContent className={styles.cardContent}>
        {title && (
          <Typography variant="subtitle2" sx={{ mb: 1, px: 0.5, textAlign: 'center' }}>
            {title}
          </Typography>
        )}
        <Box className={styles.chartContainer}>
          <ResponsiveContainer width="100%" height={height}>
            <ScatterChart 
              data={data} 
              margin={{ top: 30, right: 15, bottom: 20, left: 5 }}
            >
              {showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis 
                dataKey="x"
                type="number"
                tick={{ 
                  fontSize: getPixelFontSize(theme.typography.chartTick.fontSize),
                  fill: theme.palette.text.primary
                }}
                axisLine={{ strokeWidth: 1 }}
                tickLine={{ strokeWidth: 1 }}
                label={xAxisLabel ? { value: xAxisLabel, position: 'insideBottom', offset: -10, style: { fontSize: theme.typography.chartTick.fontSize } } : undefined}
                {...xAxisConfig}
              />
              <YAxis 
                dataKey="y"
                type="number"
                tick={{ 
                  fontSize: getPixelFontSize(theme.typography.chartTick.fontSize),
                  fill: theme.palette.text.primary
                }} 
                axisLine={{ strokeWidth: 1 }}
                tickLine={{ strokeWidth: 1 }}
                label={yAxisLabel ? { value: yAxisLabel, angle: -90, position: 'insideLeft', style: { fontSize: theme.typography.chartTick.fontSize } } : undefined}
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
