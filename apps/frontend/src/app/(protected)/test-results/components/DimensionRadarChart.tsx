'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Paper, Typography, CircularProgress, Alert, Box } from '@mui/material';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Legend } from 'recharts';
import { useTheme } from '@mui/material/styles';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultsStats, PassFailStats } from '@/utils/api-client/interfaces/test-results';
import { TestResultsStatsOptions, TestResultsStatsMode } from '@/utils/api-client/interfaces/common';

interface DimensionRadarChartProps {
  sessionToken: string;
  filters: Partial<TestResultsStatsOptions>;
  dimension: 'behavior' | 'category' | 'topic';
  title: string;
}

// Helper function to calculate number of lines for a given text
const calculateLineCount = (text: string, maxLineLength: number = 14): number => {
  if (!text) return 1;
  
  const words = text.split(' ');
  let currentLine = '';
  let lineCount = 0;
  
  for (const word of words) {
    if ((currentLine + word).length <= maxLineLength) {
      currentLine += (currentLine ? ' ' : '') + word;
    } else {
      if (currentLine) lineCount++;
      currentLine = word;
    }
  }
  if (currentLine) lineCount++;
  
  return Math.max(lineCount, 1); // Ensure at least 1 line
};

// Custom tick component for wrapping text with dynamic positioning
const CustomTick = ({ payload, x, y, textAnchor, cx, cy, ...rest }: any) => {
  const maxLineLength = 14; // Max characters per line (increased for pass rate)
  const lines = [];
  
  if (payload?.value) {
    const words = payload.value.split(' ');
    let currentLine = '';
    
    for (const word of words) {
      if ((currentLine + word).length <= maxLineLength) {
        currentLine += (currentLine ? ' ' : '') + word;
      } else {
        if (currentLine) lines.push(currentLine);
        currentLine = word;
      }
    }
    if (currentLine) lines.push(currentLine);
  }
  
  // Calculate distance from center and push labels further out based on line count
  const centerX = cx || 0;
  const centerY = cy || 0;
  const distanceFromCenter = Math.sqrt((x - centerX) ** 2 + (y - centerY) ** 2);
  
  // Additional offset based on number of lines (more lines = push further out)
  const baseOffset = 8;
  const additionalOffset = (lines.length - 1) * 6;
  const totalOffset = baseOffset + additionalOffset;
  
  // Calculate the direction vector from center to original position
  const directionX = (x - centerX) / distanceFromCenter;
  const directionY = (y - centerY) / distanceFromCenter;
  
  // Apply offset in the same direction
  const adjustedX = x + (directionX * totalOffset);
  const adjustedY = y + (directionY * totalOffset);
  
  // Adjust text anchor based on position relative to center
  let adjustedTextAnchor = textAnchor;
  if (adjustedX < centerX - 10) {
    adjustedTextAnchor = 'end';
  } else if (adjustedX > centerX + 10) {
    adjustedTextAnchor = 'start';
  } else {
    adjustedTextAnchor = 'middle';
  }
  
  return (
    <g>
      {lines.map((line, index) => (
        <text
          key={index}
          x={adjustedX}
          y={adjustedY + (index * 12) - ((lines.length - 1) * 6)} // Center multi-line text vertically
          textAnchor={adjustedTextAnchor}
          fontSize="10"
          fill="#666"
          dominantBaseline="middle"
        >
          {line}
        </text>
      ))}
    </g>
  );
};

const transformDimensionDataForRadar = (
  dimensionData?: Record<string, PassFailStats>,
  dimensionName: string = 'Item'
) => {
  if (!dimensionData) {
    // Generate mock data for demonstration
    return [
      { subject: `${dimensionName} A (90%)`, passRate: 90 },
      { subject: `${dimensionName} B (76%)`, passRate: 76 },
      { subject: `${dimensionName} C (87%)`, passRate: 87 },
      { subject: `${dimensionName} D (60%)`, passRate: 60 },
      { subject: `${dimensionName} E (84%)`, passRate: 84 }
    ];
  }

  return Object.entries(dimensionData)
    .map(([name, stats]) => {
      const total = (stats?.passed || 0) + (stats?.failed || 0);
      const passRate = total > 0 ? Math.round(((stats?.passed || 0) / total) * 100) : 0;
      
      return {
        subject: `${name || 'Unknown'} (${passRate}%)`, // Include pass rate in the label
        passRate: passRate
      };
    })
    .filter(item => item.passRate > 0) // Filter out items with no pass rate
    .sort((a, b) => b.passRate - a.passRate) // Sort by pass rate descending
    .slice(0, 5); // Top 5
};

export default function DimensionRadarChart({ 
  sessionToken, 
  filters, 
  dimension, 
  title 
}: DimensionRadarChartProps) {
  const theme = useTheme();
  const [stats, setStats] = useState<TestResultsStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();
      
      const options: TestResultsStatsOptions = {
        mode: dimension as TestResultsStatsMode, // Use specific mode for each dimension
        months: filters.months || 6,
        ...filters
      };

      const statsData = await testResultsClient.getComprehensiveTestResultsStats(options);
      if (statsData && typeof statsData === 'object') {
        setStats(statsData);
        setError(null);
      } else {
        setStats(null);
        setError(`Invalid ${dimension} data received`);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : `Failed to load ${dimension} data`;
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [sessionToken, filters, dimension]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const chartData = useMemo(() => {
    let dimensionData: Record<string, PassFailStats> | undefined;
    
    switch (dimension) {
      case 'behavior':
        dimensionData = stats?.behavior_pass_rates;
        break;
      case 'category':
        dimensionData = stats?.category_pass_rates;
        break;
      case 'topic':
        dimensionData = stats?.topic_pass_rates;
        break;
    }

    return transformDimensionDataForRadar(dimensionData, dimension);
  }, [stats, dimension]);

  // Calculate dynamic spacing based on label complexity
  const chartSpacing = useMemo(() => {
    const maxLines = Math.max(
      ...chartData.map(item => calculateLineCount(item.subject)),
      1 // Ensure at least 1 line
    );
    
    // Base margin for single-line labels
    const baseMargin = 30;
    
    // Additional spacing per extra line - labels are pushed further out
    const extraSpacingPerLine = 8;
    
    // Calculate margin based on maximum line count across all labels
    const marginSize = baseMargin + (maxLines - 1) * extraSpacingPerLine;
    
    return {
      margin: Math.min(marginSize, 80), // Cap at reasonable maximum
      maxLines
    };
  }, [chartData]);

  if (isLoading) {
    return (
      <Paper elevation={1} sx={{ p: 3, height: 400, display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Pass rates for the top 5 performing {dimension === 'category' ? 'categories' : `${dimension}s`}
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
          <CircularProgress size={24} />
          <Typography variant="body2" sx={{ ml: 2, fontSize: '0.875rem' }}>Loading {dimension}...</Typography>
        </Box>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper elevation={1} sx={{ p: 3, height: 400, display: 'flex', flexDirection: 'column' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Error occurred
        </Typography>
        <Alert severity="error">{error}</Alert>
      </Paper>
    );
  }

  return (
    <Paper elevation={1} sx={{ p: 3, height: 400, display: 'flex', flexDirection: 'column' }}>
      <Typography variant="h6" sx={{ mb: 1 }}>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Pass rates for the top 5 performing {dimension === 'category' ? 'categories' : `${dimension}s`}
      </Typography>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={chartData} margin={{ 
          top: chartSpacing.margin, 
          right: chartSpacing.margin, 
          bottom: chartSpacing.margin, 
          left: chartSpacing.margin 
        }}>
          <PolarGrid />
          <PolarAngleAxis 
            dataKey="subject" 
            tick={<CustomTick />}
          />
          <PolarRadiusAxis 
            angle={90} 
            domain={[0, 100]} 
            tick={{ fontSize: 10 }}
            tickFormatter={(value) => `${value}%`}
          />
          <Radar
            name="Pass Rate"
            dataKey="passRate"
            stroke={theme.palette.primary.main}
            fill={theme.palette.primary.main}
            fillOpacity={0.3}
            strokeWidth={2}
            dot={false}
          />

        </RadarChart>
        </ResponsiveContainer>
      </Box>
    </Paper>
  );
}
