'use client';

import React, { useEffect, useState, useRef } from 'react';
import { BasePieChart, BaseChartsGrid } from '@/components/common/BaseCharts';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestStats } from '@/utils/api-client/interfaces/tests';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';

// Fallback mock data in case the API fails
const fallbackData = [{ name: 'Loading...', value: 100 }];

// Configuration for each chart
const CHART_CONFIG = {
  behavior: { top: 5, title: 'Tests by Behavior' },
  topic: { top: 3, title: 'Tests by Topic' },
  category: { top: 5, title: 'Tests by Category' },
  status: { top: 5, title: 'Tests by Status' },
};

// Helper function to truncate long names for legends
const truncateName = (name: string): string => {
  if (name.length <= 15) return name;
  return `${name.substring(0, 12)}...`;
};

interface TestChartsProps {
  sessionToken: string;
  onLoadComplete?: () => void;
}

export default function TestCharts({
  sessionToken,
  onLoadComplete,
}: TestChartsProps) {
  // Better state tracking with a ref
  const isMountedRef = useRef(true);
  const [isInitialized, setIsInitialized] = useState(false);
  const [testStats, setTestStats] = useState<TestStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Initialize and track mounted state
  useEffect(() => {
    isMountedRef.current = true;
    setIsInitialized(true);

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Fetch data only when initialized
  useEffect(() => {
    if (!isInitialized || !sessionToken) return;

    const fetchTestStats = async () => {
      try {
        setIsLoading(true);
        const clientFactory = new ApiClientFactory(sessionToken);
        const testsClient = clientFactory.getTestsClient();

        const maxTop = Math.max(
          CHART_CONFIG.behavior.top,
          CHART_CONFIG.topic.top,
          CHART_CONFIG.category.top,
          CHART_CONFIG.status.top
        );

        const stats = await testsClient.getTestStats({
          top: maxTop,
          months: 1,
        });

        if (isMountedRef.current) {
          setTestStats(stats);
          setError(null);
        }
      } catch (err) {
        if (isMountedRef.current) {
          setError('Failed to load test statistics');
        }
      } finally {
        if (isMountedRef.current) {
          setIsLoading(false);
          // Notify parent that loading is complete
          if (onLoadComplete) {
            onLoadComplete();
          }
        }
      }
    };

    fetchTestStats();
  }, [sessionToken, isInitialized, onLoadComplete]);

  // Chart data generation functions
  const generateBehaviorData = () => {
    try {
      if (!testStats) return fallbackData;

      const { stats } = testStats;
      return Object.entries(stats.behavior.breakdown)
        .slice(0, CHART_CONFIG.behavior.top)
        .map(([name, value]) => ({
          name: truncateName(name),
          value,
          fullName: name,
        }));
    } catch (error) {
      return fallbackData;
    }
  };

  const generateTopicData = () => {
    try {
      if (!testStats) return fallbackData;

      const { stats } = testStats;
      return Object.entries(stats.topic.breakdown)
        .slice(0, CHART_CONFIG.topic.top)
        .map(([name, value]) => ({
          name: truncateName(name),
          value,
          fullName: name,
        }));
    } catch (error) {
      return fallbackData;
    }
  };

  const generateCategoryData = () => {
    try {
      if (!testStats) return fallbackData;

      const { stats } = testStats;
      return Object.entries(stats.category.breakdown)
        .slice(0, CHART_CONFIG.category.top)
        .map(([name, value]) => ({
          name: truncateName(name),
          value,
          fullName: name,
        }));
    } catch (error) {
      return fallbackData;
    }
  };

  const generateStatusData = () => {
    try {
      if (!testStats) return fallbackData;

      const { stats } = testStats;
      return Object.entries(stats.status.breakdown)
        .slice(0, CHART_CONFIG.status.top)
        .map(([name, value]) => ({
          name: truncateName(name),
          value,
          fullName: name,
        }));
    } catch (error) {
      return fallbackData;
    }
  };

  // Show loading state if not initialized
  if (!isInitialized) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show loading spinner while data is being fetched
  if (isLoading && !testStats) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show error message if data fetching failed
  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="error">{error}</Typography>
      </Box>
    );
  }

  // Render charts
  return (
    <BaseChartsGrid>
      <BasePieChart
        title={CHART_CONFIG.behavior.title}
        data={generateBehaviorData()}
        useThemeColors={true}
        colorPalette="pie"
      />

      <BasePieChart
        title={CHART_CONFIG.topic.title}
        data={generateTopicData()}
        useThemeColors={true}
        colorPalette="pie"
      />

      <BasePieChart
        title={CHART_CONFIG.category.title}
        data={generateCategoryData()}
        useThemeColors={true}
        colorPalette="pie"
      />

      <BasePieChart
        title={CHART_CONFIG.status.title}
        data={generateStatusData()}
        useThemeColors={true}
        colorPalette="pie"
      />
    </BaseChartsGrid>
  );
}
