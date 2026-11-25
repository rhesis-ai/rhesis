'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';

/** A labelled value in the schedule's summary cards. */
export default function ScheduleRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <Box sx={{ display: 'flex', gap: 2, py: 0.5 }}>
      <Typography
        variant="body2"
        color="text.secondary"
        sx={{ minWidth: theme => theme.spacing(16) }}
      >
        {label}
      </Typography>
      <Typography variant="body2" component="div">
        {value}
      </Typography>
    </Box>
  );
}
