'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { TestResultsStats } from '@/utils/api-client/interfaces/test-results';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import BaseTimelineChart from './BaseTimelineChart';
import { extractOverallData } from './timelineUtils';

interface PassRateTimelineChartProps {
  sessionToken: string;
  filters: Partial<TestResultsStatsOptions>;
}

export default function PassRateTimelineChart({
  sessionToken,
  filters,
}: PassRateTimelineChartProps) {
  const [stats, setStats] = useState<TestResultsStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const clientFactory = new ApiClientFactory(sessionToken);
      const testResultsClient = clientFactory.getTestResultsClient();

      const options: TestResultsStatsOptions = {
        mode: 'timeline', // Specific mode for timeline data
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
        err instanceof Error ? err.message : 'Failed to load timeline data';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [sessionToken, filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <BaseTimelineChart
      title="Pass Rate by Month"
      data={stats?.timeline || []}
      dataExtractor={extractOverallData}
      height={400}
      contextInfo="Monthly pass rate trends showing test performance over time"
      showMockDataFallback={true}
      isLoading={isLoading}
      error={error}
    />
  );
}
