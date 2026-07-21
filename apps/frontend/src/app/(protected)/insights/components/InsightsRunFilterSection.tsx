'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';
import { FilterSection, filterChipSx } from '@/components/common/FilterDrawer';
import {
  INSIGHTS_TIME_RANGE_OPTIONS,
  InsightsRunFilterMode,
  InsightsTimeRange,
  resolveInsightsTimeRange,
} from '../types';
import InsightsTestRunFilterSection from './InsightsTestRunFilterSection';
import { InsightsTestRunOption } from '../utils/insights-filter-utils';

interface InsightsRunFilterSectionProps {
  runFilterMode: InsightsRunFilterMode;
  timeRange: InsightsTimeRange;
  testRunOptions: InsightsTestRunOption[];
  checkedTestRunIds: string[];
  onRunFilterModeChange: (mode: InsightsRunFilterMode) => void;
  onTimeRangeChange: (timeRange: InsightsTimeRange) => void;
  onCheckedTestRunIdsChange: (ids: string[]) => void;
  testRunsLoading?: boolean;
  disabled?: boolean;
}

const MODE_OPTIONS: { value: InsightsRunFilterMode; label: string }[] = [
  { value: 'timeRange', label: 'Time range' },
  { value: 'testRuns', label: 'Test runs' },
];

export default function InsightsRunFilterSection({
  runFilterMode,
  timeRange,
  testRunOptions,
  checkedTestRunIds,
  onRunFilterModeChange,
  onTimeRangeChange,
  onCheckedTestRunIdsChange,
  testRunsLoading = false,
  disabled = false,
}: InsightsRunFilterSectionProps) {
  return (
    <FilterSection title="Scope">
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <Typography
            sx={{
              fontSize: 14,
              lineHeight: '22px',
              color: theme => theme.palette.greyscale.body,
            }}
          >
            Filter by
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {MODE_OPTIONS.map(option => (
              <Box
                key={option.value}
                component="button"
                type="button"
                disabled={disabled}
                onClick={() => onRunFilterModeChange(option.value)}
                sx={filterChipSx(runFilterMode === option.value)}
              >
                {option.label}
              </Box>
            ))}
          </Box>
        </Box>

        {runFilterMode === 'timeRange' ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <Typography
              sx={{
                fontSize: 14,
                lineHeight: '22px',
                color: theme => theme.palette.greyscale.body,
              }}
            >
              Time range
            </Typography>
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
            <Typography
              sx={{
                fontSize: 12,
                lineHeight: '18px',
                color: 'text.secondary',
                pt: '3px',
              }}
            >
              Includes all test runs created within the selected window.
            </Typography>
          </Box>
        ) : (
          <InsightsTestRunFilterSection
            embedded
            options={testRunOptions}
            checkedIds={checkedTestRunIds}
            onCheckedIdsChange={onCheckedTestRunIdsChange}
            loading={testRunsLoading}
            disabled={disabled}
          />
        )}
      </Box>
    </FilterSection>
  );
}
