'use client';

import * as React from 'react';
import { Chip, Typography } from '@mui/material';
import {
  RUN_STATUS_COLOR,
  RUN_STATUS_ICON,
  RUN_STATUS_LABEL,
  type RunStatus,
} from '@/constants/test-runs';

export default function RunStatusChip({ status }: { status?: string | null }) {
  const key = (status ?? '').toLowerCase() as RunStatus;
  if (!RUN_STATUS_LABEL[key]) {
    return (
      <Typography variant="body2" color="text.secondary">
        {status ?? '—'}
      </Typography>
    );
  }
  const Icon = RUN_STATUS_ICON[key];
  return (
    <Chip
      icon={<Icon />}
      label={RUN_STATUS_LABEL[key]}
      color={RUN_STATUS_COLOR[key]}
      size="small"
      sx={{ fontWeight: 600 }}
    />
  );
}
