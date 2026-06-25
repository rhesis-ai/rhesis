'use client';

import React from 'react';
import { Box, LinearProgress, Typography } from '@mui/material';
import { PassFailStats } from '@/utils/api-client/interfaces/test-results';
import { formatInsightsSummaryDetail } from '../utils/insights-failed-tests';

interface InsightsSummaryBarProps {
  summary: PassFailStats | null;
  endpointName?: string;
  loading?: boolean;
  failedTestCaseCount?: number | null;
}

function progressColor(passRate: number): 'success' | 'warning' | 'error' {
  if (passRate >= 70) return 'success';
  if (passRate >= 40) return 'warning';
  return 'error';
}

export default function InsightsSummaryBar({
  summary,
  endpointName,
  loading = false,
  failedTestCaseCount,
}: InsightsSummaryBarProps) {
  const passRate = summary?.pass_rate ?? 0;
  const passed = summary?.passed ?? 0;
  const total = summary?.total ?? 0;
  const failed = summary?.failed ?? 0;
  const barColor = progressColor(passRate);

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
        {loading ? (
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
              {formatInsightsSummaryDetail(
                passed,
                total,
                failed,
                failedTestCaseCount ?? undefined
              )}
              {endpointName ? ` · ${endpointName}` : ''}
            </Typography>
          </>
        )}
      </Typography>

      <LinearProgress
        variant={loading ? 'indeterminate' : 'determinate'}
        value={loading ? undefined : passRate}
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
