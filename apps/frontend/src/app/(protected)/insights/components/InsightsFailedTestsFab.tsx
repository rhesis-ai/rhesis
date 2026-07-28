'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { Fab } from '@/components/common/Fab';
import { ScienceIcon } from '@/components/icons';
import { InsightsFilters } from '../types';
import { buildInsightsFailedTestsUrl } from '../utils/insights-failed-tests';
import {
  insightsOverallFailedScope,
  prefetchInsightsFailedTestIds,
} from '@/hooks/useInsightsFailedTestIds';

interface InsightsFailedTestsFabProps {
  filters: InsightsFilters;
  failedCount: number;
  loading?: boolean;
  disabled?: boolean;
}

export default function InsightsFailedTestsFab({
  filters,
  failedCount,
  loading = false,
  disabled = false,
}: InsightsFailedTestsFabProps) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const isDisabled =
    disabled || loading || !filters.endpointId || failedCount === 0;

  const handleClick = () => {
    if (isDisabled) return;
    const scope = insightsOverallFailedScope(filters);
    void prefetchInsightsFailedTestIds(queryClient, scope);
    router.push(buildInsightsFailedTestsUrl(filters));
  };

  return (
    <Fab
      icon={<ScienceIcon />}
      tooltip={
        failedCount > 0
          ? `View ${failedCount} failed test case${failedCount === 1 ? '' : 's'}`
          : 'No failed test cases in this view'
      }
      aria-label="View failed test cases"
      onClick={handleClick}
      disabled={isDisabled}
    />
  );
}
