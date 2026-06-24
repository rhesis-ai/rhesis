'use client';

import React from 'react';
import { Box, LinearProgress, Typography } from '@mui/material';
import { PassFailStats } from '@/utils/api-client/interfaces/test-results';

interface InsightsSummaryBarProps {
  summary: PassFailStats | null;
  endpointName?: string;
  loading?: boolean;
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

  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          gap: 1,
          mb: 1.5,
        }}
      >
        <Typography variant="h5" fontWeight={700} component="span">
          {loading ? '—' : `${passRate.toFixed(1)}%`}
        </Typography>
        <Typography variant="body1" color="text.secondary" component="span">
          Pass Rate
        </Typography>
        {endpointName && (
          <Typography
            variant="body2"
            color="text.secondary"
            component="span"
            sx={{ ml: { sm: 0.5 } }}
          >
            · {endpointName}
          </Typography>
        )}
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {loading
          ? 'Loading results…'
          : `${passed}/${total} tests passed${failed > 0 ? ` (${failed} failed)` : ''}`}
      </Typography>

      <LinearProgress
        variant={loading ? 'indeterminate' : 'determinate'}
        value={loading ? undefined : passRate}
        sx={{
          height: 6,
          borderRadius: 3,
          bgcolor: theme => theme.palette.action.hover,
          '& .MuiLinearProgress-bar': {
            borderRadius: 3,
            bgcolor: theme =>
              passRate >= 70
                ? theme.palette.success.main
                : passRate >= 40
                  ? theme.palette.warning.main
                  : theme.palette.error.main,
          },
        }}
      />
    </Box>
  );
}
