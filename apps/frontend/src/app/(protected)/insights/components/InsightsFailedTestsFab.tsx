'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { Fab, FabGroup } from '@/components/common/Fab';
import { ScienceIcon } from '@/components/icons';
import { InsightsFilters } from '../types';
import { buildInsightsFailedTestsUrl } from '../utils/insights-failed-tests';

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

  const isDisabled =
    disabled || loading || !filters.endpointId || failedCount === 0;

  const handleClick = () => {
    if (isDisabled) return;
    router.push(buildInsightsFailedTestsUrl(filters));
  };

  return (
    <FabGroup>
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
    </FabGroup>
  );
}
