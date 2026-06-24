'use client';

import React from 'react';
import { Box, Chip, Paper, Skeleton, Typography } from '@mui/material';
import { getReviewBand } from '@/app/(protected)/test-runs/[identifier]/components/test-run-summary-utils';
import { BehaviorInsightColumn } from '../utils/behavior-insights-utils';
import {
  BehaviorMetricList,
  BehaviorTopicList,
} from './BehaviorDimensionLists';

interface BehaviorColumnProps {
  column: BehaviorInsightColumn;
  loading?: boolean;
}

export default function BehaviorColumn({
  column,
  loading = false,
}: BehaviorColumnProps) {
  const band = getReviewBand(column.overall.pass_rate);

  if (loading) {
    return (
      <Paper
        variant="outlined"
        sx={{
          p: 2,
          borderRadius: 2,
          minWidth: 260,
          maxWidth: 320,
          flex: '0 0 auto',
        }}
      >
        <Skeleton width="60%" height={28} />
        <Skeleton width="40%" sx={{ mt: 1 }} />
        <Skeleton height={120} sx={{ mt: 2 }} />
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        borderRadius: 2,
        minWidth: 260,
        maxWidth: 320,
        flex: '0 0 auto',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 1,
          mb: 2,
          pb: 1.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Typography
          variant="subtitle1"
          fontWeight={700}
          sx={{ lineHeight: 1.3 }}
        >
          {column.name}
        </Typography>
        <Chip
          label={`${column.overall.pass_rate.toFixed(0)}%`}
          size="small"
          color={band.colorKey}
          sx={{ fontWeight: 600, flexShrink: 0 }}
        />
      </Box>

      <Typography variant="caption" color="text.secondary" sx={{ mb: 1.5 }}>
        {column.overall.passed}/{column.overall.total} passed
      </Typography>

      <BehaviorMetricList items={column.metrics} />
      <BehaviorTopicList items={column.topics} />
    </Paper>
  );
}
