'use client';

import React from 'react';
import { Box, LinearProgress, Typography } from '@mui/material';
import { useSkeletonMode } from '@/components/loading/SkeletonMode';
import {
  PLACEHOLDER_TEXT,
  TextPlaceholder,
} from '@/components/loading/TextPlaceholder';
import { PassFailStats } from '@/utils/api-client/interfaces/test-results';
import { formatInsightsSummaryDetail } from '../utils/insights-failed-tests';
import { getReviewBand } from '@/constants/outcomes';

interface InsightsSummaryBarProps {
  summary: PassFailStats | null;
  endpointName?: string;
  loading?: boolean;
}

// One shared scale (constants/outcomes.ts). This widget used to band at
// 70/40 while the requirement columns on the same page banded at 100/70, so
// the same rate could be green here and red one card over.
function progressColor(passRate: number): 'success' | 'warning' | 'error' {
  return getReviewBand(passRate).colorKey;
}

export default function InsightsSummaryBar({
  summary,
  endpointName,
  loading = false,
}: InsightsSummaryBarProps) {
  const passRate = summary?.pass_rate ?? 0;
  const passed = summary?.passed ?? 0;
  const total = summary?.total ?? 0;
  const failed = summary?.failed ?? 0;
  const barColor = progressColor(passRate);
  // In a loading view the figures are placeholders and the bar an empty track.
  const skeleton = useSkeletonMode();

  return (
    <Box
      sx={{
        px: 1.75,
        py: 1.25,
        borderRadius: 1.5,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <Typography
        variant="body2"
        sx={{ mb: 0.75, lineHeight: 1.45, color: 'text.primary' }}
      >
        {skeleton ? (
          <TextPlaceholder>{PLACEHOLDER_TEXT.long}</TextPlaceholder>
        ) : loading ? (
          <Box component="span" sx={{ color: 'text.secondary' }}>
            Loading results…
          </Box>
        ) : (
          <>
            <Box component="span" sx={{ fontWeight: 600 }}>
              {passRate.toFixed(1)}%
            </Box>
            {' Pass Rate '}
            <Typography
              component="span"
              variant="caption"
              sx={{ color: 'text.disabled', fontWeight: 400 }}
            >
              {formatInsightsSummaryDetail(passed, total, failed)}
              {endpointName ? ` · ${endpointName}` : ''}
            </Typography>
          </>
        )}
      </Typography>

      <LinearProgress
        aria-label={loading ? 'Loading pass rate' : 'Pass rate'}
        variant={loading && !skeleton ? 'indeterminate' : 'determinate'}
        value={skeleton ? 0 : loading ? undefined : passRate}
        color={loading ? 'primary' : barColor}
        sx={{
          height: 4,
          borderRadius: 2,
          bgcolor: theme => theme.palette.action.hover,
          '& .MuiLinearProgress-bar': {
            borderRadius: 2,
          },
        }}
      />
    </Box>
  );
}
