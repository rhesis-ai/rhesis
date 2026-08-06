'use client';

import * as React from 'react';
import { Box } from '@mui/material';
import { FilterSection, filterChipSx } from '@/components/common/FilterDrawer';
import {
  INSIGHTS_TIME_RANGE_OPTIONS,
  InsightsTimeRange,
  resolveInsightsTimeRange,
} from '../types';

interface InsightsTimeRangeFilterSectionProps {
  timeRange: InsightsTimeRange;
  onTimeRangeChange: (timeRange: InsightsTimeRange) => void;
  disabled?: boolean;
}

export default function InsightsTimeRangeFilterSection({
  timeRange,
  onTimeRangeChange,
  disabled = false,
}: InsightsTimeRangeFilterSectionProps) {
  return (
    <FilterSection title="Time range">
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {INSIGHTS_TIME_RANGE_OPTIONS.map(option => (
          <Box
            key={option.value}
            component="button"
            type="button"
            disabled={disabled}
            onClick={() => onTimeRangeChange(option.value)}
            sx={filterChipSx(
              resolveInsightsTimeRange(timeRange) === option.value
            )}
          >
            {option.label}
          </Box>
        ))}
      </Box>
    </FilterSection>
  );
}
