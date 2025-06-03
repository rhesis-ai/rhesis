import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { Typography, Box, Card, CardContent } from '@mui/material';
import { useChartColors } from './BaseChartColors';

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
      .replace(/_/g, ' ')         // Convert snake_case to space separated
      .toLowerCase()
      .trim();
    
    // Capitalize first letter of each word
    return `Tests by ${formatted.split(' ')
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
          percentage: `${percentage}%` // Add percentage for tooltip
        };
      });
  }
};

// Custom label rendering function to position labels closer to the chart segments
const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index, name }: any) => {
  // Calculate the position for the label
  const RADIAN = Math.PI / 180;
  // Position labels just outside the pie chart (20% beyond the outer radius)
  const radius = outerRadius * 1.25;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  
  // Determine if the label is on the right side or left side of the chart
  const isRightSide = x > cx;
  
  // Only show labels for segments with significant percentage (helps prevent overlap)
  if (percent < 0.05) return null;
  
  return (
    <text 
      x={x} 
      y={y} 
      fill="#333333" // Dark grey for better visibility on light backgrounds
      textAnchor={isRightSide ? "start" : "end"}
      dominantBaseline="central"
      fontSize="11px"
      fontWeight="bold"
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

// Custom label line rendering function
const renderCustomizedLabelLine = ({ cx, cy, midAngle, outerRadius }: any) => {
  const RADIAN = Math.PI / 180;
  const startRadius = outerRadius + 2;
  const endRadius = outerRadius * 1.2;
  
  const x1 = cx + startRadius * Math.cos(-midAngle * RADIAN);
  const y1 = cy + startRadius * Math.sin(-midAngle * RADIAN);
  const x2 = cx + endRadius * Math.cos(-midAngle * RADIAN);
  const y2 = cy + endRadius * Math.sin(-midAngle * RADIAN);
  
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
  legendProps = { 
    wrapperStyle: { fontSize: '10px' }, 
    iconSize: 8,
    layout: 'horizontal',
    verticalAlign: 'bottom',
    align: 'center'
  },
  tooltipProps = { contentStyle: { fontSize: '10px' } }
}: BasePieChartProps) {
  // Get theme colors
  const { palettes } = useChartColors();
  
  // Decide which color palette to use
  // Priority: 1. Custom colors 2. Theme palette specified 3. Default theme pie palette
  const defaultColors = ['#8884d8', '#82ca9d', '#ffc658', '#ff8042', '#0088FE'];
  const chartColors = colors || (useThemeColors ? (palettes[colorPalette] || defaultColors) : defaultColors);
  
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ p: 0.5, height: '100%', display: 'flex', flexDirection: 'column', '&:last-child': { pb: 0.5 } }}>
        {title && (
          <Typography variant="subtitle1" sx={{ mb: 1, fontSize: '0.875rem', px: 0.5, textAlign: 'center', fontWeight: 'bold' }}>
            {title}
          </Typography>
        )}
        <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <ResponsiveContainer width="100%" height={height}>
            <PieChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={innerRadius}
                outerRadius={outerRadius}
                paddingAngle={2}
                fill="#8884d8"
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
              <Tooltip 
                {...tooltipProps} 
                formatter={(value, name, props) => {
                  const item = data.find(d => d.name === name);
                  return [value, item?.fullName || name];
                }}
              />
              <Legend {...legendProps} />
            </PieChart>
          </ResponsiveContainer>
        </Box>
      </CardContent>
    </Card>
  );
} 