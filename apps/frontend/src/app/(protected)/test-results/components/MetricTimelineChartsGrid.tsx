'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  Alert,
  CircularProgress,
  useTheme,
  Paper,
} from '@mui/material';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultsStats } from '@/utils/api-client/interfaces/test-results';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import MetricTimelineChart from './MetricTimelineChart';

interface MetricTimelineChartsGridProps {
  sessionToken: string;
  filters: Partial<TestResultsStatsOptions>;
}

// Extract unique metric names from timeline data
const extractUniqueMetrics = (
  timeline?: Array<{
    date: string;
    overall: any;
    metrics?: Record<string, any>;
  }>
) => {
  if (!timeline || timeline.length === 0) return [];

  const metricNames = new Set<string>();

  timeline.forEach(item => {
    if (item.metrics) {
      Object.keys(item.metrics).forEach(metricName => {
        metricNames.add(metricName);
      });
    }
  });

  return Array.from(metricNames).sort();
};

export default function MetricTimelineChartsGrid({
  sessionToken,
  filters,
}: MetricTimelineChartsGridProps) {
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
        mode: 'timeline', // Use timeline mode to get metric breakdown
        months: filters.months || 6,
        ...filters,
      };

      const statsData =
        await testResultsClient.getComprehensiveTestResultsStats(options);
      if (statsData && typeof statsData === 'object') {
        setStats(statsData);
        setError(null);
      } else {
        setStats(null);
        setError('Invalid timeline data received');
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : 'Failed to load metrics timeline data';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [sessionToken, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const uniqueMetrics = useMemo(() => {
    return extractUniqueMetrics(stats?.timeline);
  }, [stats?.timeline]);

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 400,
        }}
      >
        <CircularProgress size={24} />
        <Typography variant="helperText" sx={{ ml: 2 }}>
          Loading metrics timeline...
        </Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!stats?.timeline || uniqueMetrics.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography variant="h6" color="text.secondary">
          No metric timeline data available
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          Timeline data does not contain metric breakdowns for the selected
          period.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        Individual Metric Performance Over Time
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Track pass rates for each metric across the selected time period. Found{' '}
        {uniqueMetrics.length} metrics.
      </Typography>

      {/* Responsive grid for metric charts */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr', // 1 column on mobile
            sm: '1fr 1fr', // 2 columns on small screens
            md: '1fr 1fr', // 2 columns on medium screens
            lg: '1fr 1fr 1fr', // 3 columns on large screens
            xl: '1fr 1fr 1fr 1fr', // 4 columns on extra large screens
          },
          gap: theme.customSpacing.section.medium,
        }}
      >
        {uniqueMetrics.map(metricName => (
          <MetricTimelineChart
            key={metricName}
            metricName={metricName}
            timelineData={stats.timeline || []}
          />
        ))}
      </Box>
    </Box>
  );
}
